# Ryu-Broadcast
A Ryu application to handle the broadcast routing algorithm

How to set up simple_switch_stp_13.py and spanning_tree.py for testing.

1. When launching simple_switch_stp_13.py in a terminal, there should be three messages warning that the switches are using the incorrect version of OpenFlow.

2. Launch spanning_tree.py after simple_switch_stp_13.py. When launching spanning_tree.py in another terminal, XQuartz should create xterm terminals for the controller, all switches, and all hosts.

3. Within the xterm terminals for switches, enter the command `ovs-vsctl set Bridge <switch> protocols=OpenFlow13`. `<switch>` should be replaced with the name of the switch the terminal belongs to, ex. `ovs-vsctl set Bridge s2 protocols=OpenFlow13` should be entered inside the xterm terminal belonging to s2. This step should fix the warning messages from step 1. Additionally, `tcpdump -i <switch>-eth2 arp` can be entered in the switch xterm terminals after the ovs-vsctl command. This command provides more information on what travels through a switch. 

4. The terminal running simple_switch_stp_13.py should now print out updates about the state of switch ports.
