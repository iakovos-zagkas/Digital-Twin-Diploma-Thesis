import os
import argparse
import pynetbox
import glob
import yaml
import ipaddress
import subprocess
from jinja2 import Environment, FileSystemLoader

parser = argparse.ArgumentParser()
parser.add_argument('--site', required=True)
parser.add_argument('--dir', default='demo')
parser.add_argument('--teardown', action='store_true')
args = parser.parse_args()

NETBOX_URL = 'http://twin.cn.ntua.gr:8000'
NETBOX_TOKEN = '1234567890123456789012345678901234567890'

nb = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)

# Teardown: If I run the script with --teardown, it removes the bridges and stops here
if args.teardown:
    devices = nb.dcim.devices.filter(site=args.site, status='active')
    for device in devices:
        if device.role.slug == 'bridge':
            subprocess.run(['sudo', 'ip', 'link', 'set', device.name, 'down'])
            subprocess.run(['sudo', 'brctl', 'delbr', device.name])
    exit()

env = Environment(loader=FileSystemLoader('templates'))
template = env.get_template('frr.j2')

if not os.path.exists(args.dir):
    os.makedirs(args.dir)

devices = nb.dcim.devices.filter(site=args.site, status='active')

linux_pcs_data = {}
bridges_data = []

for device in devices:
    if device.platform and device.platform.slug == 'frr':
        tags = [tag.slug for tag in device.tags]
        device_asn = device.custom_fields.get('bgp_asn')
        interfaces_data = []
        bgp_peers = []
        bgp_networks = []
        router_id = None

        interfaces = nb.dcim.interfaces.filter(device_id=device.id)
        for intf in interfaces:
            ips = list(nb.ipam.ip_addresses.filter(interface_id=intf.id))
            ipv4 = ips[0].address if ips else None

            if ipv4 and not router_id:
                router_id = ipv4
            if intf.custom_fields.get('bgp_advertise_network') and ipv4:
                network_prefix = str(ipaddress.IPv4Interface(ipv4).network)
                if network_prefix not in bgp_networks:
                    bgp_networks.append(network_prefix)

            ospf_area = intf.custom_fields.get('ospf_area') if intf.custom_fields.get('ospf_area') else '0.0.0.0'

            ipv4_network = str(ipaddress.IPv4Interface(ipv4).network) if ipv4 else None  #ypologismos toy katharou diktyou, den einai shmantiko

            interfaces_data.append({
                'name': intf.name,
                'description': intf.description,
                'ipv4': ipv4,
                'custom_fields': {'ospf_area': ospf_area}
            })

            if 'bgp' in tags and intf.connected_endpoints:
                peer_intf = intf.connected_endpoints[0]
                peer_device = nb.dcim.devices.get(peer_intf.device.id)
                peer_ips = list(nb.ipam.ip_addresses.filter(interface_id=peer_intf.id))
                peer_ipv4 = peer_ips[0].address if peer_ips else None
                peer_asn = peer_device.custom_fields.get('bgp_asn')

                if peer_ipv4 and peer_asn:
                    bgp_peers.append({
                        'ipv4': peer_ipv4,
                        'asn': peer_asn
                    })

        static_routes = []
        sr_field = device.custom_fields.get('static_routes')

        if sr_field:
            for route_text in sr_field.split(','):
                parts = route_text.strip().split()
                if len(parts) == 2:
                    static_routes.append({'network': parts[0], 'nexthop': parts[1]})

        data = {
            'name': device.name,
            'interfaces': interfaces_data,
            'tags': tags,
            'ipv4': router_id,
            'asn': device_asn,
            'bgp_peers': bgp_peers,
            'bgp_networks': bgp_networks,
            'static_routes': static_routes
        }
        config_text = template.render(data)
        file_path = f"{args.dir}/{device.name}.config"
        with open(file_path, "w") as f:
            f.write(config_text)

    elif device.platform and device.platform.slug == 'linux' and device.role.slug != 'bridge':
        gw = device.custom_fields.get('default_gateway')
        pc_ip = None
        pc_intf_name = None

        interfaces = nb.dcim.interfaces.filter(device_id=device.id)
        for intf in interfaces:
            ips = list(nb.ipam.ip_addresses.filter(interface_id=intf.id))
            if ips:
                pc_ip = ips[0].address
                pc_intf_name = intf.name
                break

        linux_pcs_data[device.name] = {
            'gw': gw,
            'ip': pc_ip,
            'intf': pc_intf_name
        }

    elif device.role.slug == 'bridge':
        bridges_data.append(device.name)
        subprocess.run(['sudo', 'brctl', 'addbr', device.name])
        subprocess.run(['sudo', 'ip', 'link', 'set', device.name, 'up'])


daemons_path = f"{args.dir}/daemons"
with open(daemons_path, "w") as f:
    f.write("zebra=yes\nbgpd=yes\nospfd=yes\nripd=yes\n")

clab_files = glob.glob(f"{args.dir}/*.clab.yaml")
if clab_files:
    for clab_file in clab_files:
        with open(clab_file, 'r') as f:
            clab_data = yaml.safe_load(f)
        nodes = clab_data.get('topology', {}).get('nodes', {})
        modified = False

        for node_name, node_info in nodes.items():
            if 'frr' in str(node_info.get('image', '')).lower() or str(node_info.get('platform', '')).lower() == 'frr':
                if 'binds' not in node_info:
                    node_info['binds'] = []
                config_bind = f"{node_name}.config:/etc/frr/frr.conf"
                daemon_bind = "daemons:/etc/frr/daemons"

                if config_bind not in node_info['binds']:
                    node_info['binds'].append(config_bind)
                if daemon_bind not in node_info['binds']:
                    node_info['binds'].append(daemon_bind)
                modified = True

            elif node_name in linux_pcs_data:
                if 'exec' not in node_info:
                    node_info['exec'] = []
                pc_data = linux_pcs_data[node_name]
                if pc_data['ip'] and pc_data['intf']:
                    ip_cmd = f"ip addr add {pc_data['ip']} dev {pc_data['intf']}"
                    if ip_cmd not in node_info['exec']:
                        node_info['exec'].append(ip_cmd)
                if pc_data['gw']:
                    gw_cmd = f"ip route replace default via {pc_data['gw']}"
                    if gw_cmd not in node_info['exec']:
                        node_info['exec'].append(gw_cmd)

                modified = True

            elif node_name in bridges_data:
                node_info['kind'] = 'bridge'
                if 'image' in node_info:
                    del node_info['image']
                modified = True


        if modified:
            with open(clab_file, 'w') as f:
                yaml.dump(clab_data, f, default_flow_style=False, sort_keys=False)

