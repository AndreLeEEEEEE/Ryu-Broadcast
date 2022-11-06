from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import dpid as dpid_lib
from ryu.lib import stplib
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.app import simple_switch_13

class SimpleSwitch13(simple_switch_13.SimpleSwitch13):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {"stplib": stplib.Stp}

    def __init__(self, *args, **kwargs):
        # Inherit from simple_switch_13 because the latter serves
        # as the basis for ignoring seen-before packets 
        super(SimpleSwitch13, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.stp = kwargs["stplib"]
        # Set the data path ID to all bridges on the switch
        config = {
            dpid_lib.str_to_dpid("0000000000000001"): {"bridge": {"priority": 0x8000}},
            dpid_lib.str_to_dpid("0000000000000002"): {"bridge": {"priority": 0x9000}},
            dpid_lib.str_to_dpid("0000000000000003"): {"bridge": {"priority": 0xa000}}
        }
        self.stp.set_config(config)

    @set_ev_cls(stplib.EventPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        """Handle incoming packets."""
        # The packet_in
        msg = ev.msg
        # The switch the packet is headed for
        datapath = msg.datapath
        # A representation of the OpenFlow protocol between the switch and Ryu
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        # The port number that the message came through
        in_port = msg.match["in_port"]

        # Create a new packet from the data instead of
        # mindlessly forwarding it
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})
        # Packet
        dst = eth.dst
        src = eth.src
        # Print out the packet info
        self.logger.info("packet with dpid=%s, src=%s, dst%s, and in_port%s", dpid, src, dst, in_port)
        # Put the packet_in's entry port with its 
        # the datapath ID and source 
        self.mac_to_port[dpid][src] = in_port
        # If this datapath ID is already known,
        # Pull the destination from the MAC table
        # Else, send the packet on all ports 
        out_port = self.mac_to_port[dpid][dst] if dst in self.mac_to_port[dpid] else ofproto.OFPP_FLOOD
        # Set the port(s) to send the packet out of
        actions = [parser.OFPActionOutput(out_port)]
        # In the event that the destination is pulled from the MAC table,
        # update the switch's flow table
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            # Use add_flow() from the parent class to 
            # add this type of packet to the flow table
            self.add_flow(datapath, 1, match, actions)

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data
        # Send the new packet
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                    in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    @set_ev_cls(stplib.EventTopologyChange, MAIN_DISPATCHER)
    def _topology_change_handler(self, ev):
        """Handle topology changes."""
        dp = ev.dp
        # Get the ID of the datapath
        dpid_str = dpid_lib.dpid_to_str(dp.id)
        msg = "Topology changed, clearing MAC table."
        self.logger.debug("[dpid=%s] %s", dpid_str, msg)
        # Check the list of entries in the switch's mac table
        if dp.id in self.mac_to_port:
            # Get OpenFlow protocol between Ryu and this switch
            ofp = dp.ofproto
            ofp_parser = dp.ofproto_parser
            for dst in self.mac_to_port[dp.id].keys():
                # Delete the entries in the flow table
                match = ofp_parser.OFPMatch(eth_dst=dst)
                mod = ofp_parser.OFPFlowMod( dp, command=ofp.OFPFC_DELETE,
                                            out_port=ofp.OFPP_ANY, out_group=ofp.OFPG_ANY,
                                            priority=1, match=match)
                dp.send_msg(mod)
            del self.mac_to_port[dp.id]

    @set_ev_cls(stplib.EventPortStateChange, MAIN_DISPATCHER)
    def _port_state_change_handler(self, ev):
        """Activate when the a port undergoes a state change."""
        # Get the ID of the datapath
        dpid_str = dpid_lib.dpid_to_str(ev.dp.id)
        # Set which states exist
        of_state = {
            stplib.PORT_STATE_DISABLE: "DISABLE",
            stplib.PORT_STATE_BLOCK: "BLOCK",
            stplib.PORT_STATE_LISTEN: "LISTEN",
            stplib.PORT_STATE_LEARN: "LEARN",
            stplib.PORT_STATE_FORWARD: "FORWARD"
        }
        # Print out which state a port changed to
        self.logger.debug("[dpid=%s], [port=%d], state=%s", dpid_str,
                             ev.port_no, of_state[ev.port_state])