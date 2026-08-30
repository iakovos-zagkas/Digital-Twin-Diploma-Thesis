# Digital-Twin-Diploma-Thesis
Complete walkthrough of how to create a digital twin of a network topology.

This diploma thesis deploys the digital twins of various network topologies, using a mechanism that develops both the structure of thw topology and thw configurations files of the devices in a fully automated way. This README file contains the most significant instructions in order to explain how to create such digital twins with the particular mechanism.

At first, the user has to download the software tools that are necessary for the process. The tools that are needed are : Docker, NetBox, Containerlab, nrx. More detailed instructions for downloading the above tools could be found in the formal pages of the tools or in the corresponding chapters of this thesis. Then, the user has to store the files 'build_configurations.py' and 'frr.j2' in the laboratory directory for the digital twin in order to use them later in the pipeline.

As soon as the experimental environment has been created, the next Step is to create the network topology in NetBox. Very useful tips and instructions can be found in the corresponding chapter of the diploma thesis, because some particular conditions have to be met for the successful creation of the topology. Also, NetBox offers some customization tools, such as Custom Fields and Tags, that have been utilized for the topology development.

After the creation of the network topology, the nrx tool is used in order to extract the structure of the topology (nodes - devices, cables) through the REST Api of NetBox. The following code commands are those that complete this task:
```
export NB_API_URL='...'
export NB_API_TOKEN='...'  /// connection to the NetBox API
nrx --output clab --dir demo --site <my-Site>  ///extraction of the network topology
```

In the experimental pipeline for developing digital twins, the next step of the procedure is to create the configuration files of the topology's devices, in order to build a fully functional twin of the real topology. For this step, the Python Script and the Jinja2 Template are used by executing the following command:

```
python build_configurations.py --dir demo --site <my-site>
```

Finally, the last step of the process is to deploy the digital twin in the emulation environment Containerlab by executing the following command:

```
sudo -E containerlab deploy -t demo/<my-Site>.clab.yaml (--reconfigure)
```
After that, the user has created and deployed a fully functional digital twin of a particular network topology and is able to conduct various tests in order to check the correctness of the mechanism and execute the updates or the changes that are necessary in the network topology.


This repository contains a series of digital twins of network topologies that are created through the exact mechanism that was presented above. This mechanism and experimental pipeline has been developed completely as part of my diploma thesis at NTUA titled as 'Development of digital twins of network topologies using emulation environments'.

Each folder of this repository contains all the files that are created in a fully automated way from the experimental pipeline, including router configuartion files and YAML files, for different network topologies. The topologies use various routing protocols and switching mechanisms, such as RIP, OSPF, BGP, Linux Bridges and Static Routing.
