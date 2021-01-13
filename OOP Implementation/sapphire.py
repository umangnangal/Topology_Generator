import paramiko
import pandas as pd
import re
import os
import logging
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

# Setting pandas config
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', None)

# Fetching passwords from user-provided excel sheet and storing it in a dictionary
if os.path.isfile('device_password_mapping.xlsx'):
    df = pd.read_excel('device_password_mapping.xlsx')
    print(df.head())
    device_password_mapping = dict()
    for i in range(df.shape[0]):
        device_password_mapping[df['Management IP'][i]] = df['Password'][i]
    #print(device_password_mapping)
else:
    print("Please create file 'device_password_mapping.xlsx' with Switchname and Password as Header.")

def get_switch_port(fabric, vsan, identifier_type, indentifier):
    #print('Getting switch_port for fcid {}'.format(fcid))
    for switch in fabric.devices:
        #print('Searching for FCID {} in switch {}'.format(fcid, switch.switchname))
        flogi_df = switch.get_flogi_database(vsan)
        if identifier_type == 'fcid':
            port = flogi_df.loc[flogi_df['FCID'] == indentifier]['Interface'].values
        elif identifier_type == 'pwwn':
            port = flogi_df.loc[flogi_df['PORT NAME'] == indentifier]['Interface'].values
        else:
            continue
            
        if len(port) == 1:
            #print('FCID found')
            switch_port = switch.switchname + '_' + port[0]
            return switch_port
        else:
            #print('FCID {} not found, going to next switch...')
            continue
    return None
    

class App:

    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        # Don't forget to close the driver connection when you are finished with it
        self.driver.close()

    def create_port_node(self, parent_switch, interface):
        with self.driver.session() as session:
            # Write transactions allow the driver to handle retries and transient errors
            result = session.write_transaction(
                self._create_and_return_port_node, parent_switch, interface)

    @staticmethod
    def _create_and_return_port_node(tx, parent_switch, interface):
        query = (
            "MERGE (p1:Switch { name: $switchname }) "
            "MERGE (p2:Port { name: $switchname + '_' + $interface }) "
            "MERGE (p1)-[:child_port]->(p2) "
            "RETURN p1, p2"
        )
        tx.run(query, switchname=parent_switch, interface=interface)

    def create_link(self, switch, other, link_type):
        with self.driver.session() as session:
            # Write transactions allow the driver to handle retries and transient errors
            result = session.write_transaction(
                self._create_and_return_link, switch, other, link_type)
            '''
            for record in result:
                print("Created link between: {p1}, {p2}".format(
                    p1=record['p1'], p2=record['p2']))
            '''


    @staticmethod
    def _create_and_return_link(tx, node1, node2, link_type):

        # To learn more about the Cypher syntax,
        # see https://neo4j.com/docs/cypher-manual/current/

        # The Reference Card is also a good resource for keywords,
        # see https://neo4j.com/docs/cypher-refcard/current/
        if link_type == 'N':
            query = (
                "MERGE (p1:Port { name: $switch_port }) "
                "MERGE (p2:Device { fcid: $fcid }) "
                "MERGE (p1)-[:TBD]->(p2) "
                "RETURN p1, p2"
            )
            result = tx.run(query, switch_port=node1, fcid=node2)
            
        elif link_type == 'E':
            query = (
                "MERGE (p1:Switch { name: $switch1 }) "
                "MERGE (p2:Switch { name: $switch2 }) "
                "MERGE (p1)-[:E_LINK]->(p2) "
                "RETURN p1, p2"
            )
            result = tx.run(query, switch1=node1, switch2=node2)
            
        elif link_type == 'V':
            query = (
                "MERGE (p1:Port { name: $switch_port1 }) "
                "MERGE (p2:Port { name: $switch_port2 }) "
                "MERGE (p1)-[:V_Link]->(p2) "
                "RETURN p1, p2"
            )
            result = tx.run(query, switch_port1=node1, switch_port2=node2)

    def find_switch(self, switchname):
        with self.driver.session() as session:
            result = session.read_transaction(self._find_and_return_switch, switchname)
            '''
            for record in result:
                print("Found switch: {record}".format(record=record))
            '''


    @staticmethod
    def _find_and_return_switch(tx, switchname):
        query = (
            "MATCH (p:Switch) "
            "WHERE p.name = $switchname "
            "RETURN p.name AS switchname"
        )
        result = tx.run(query, switchname=switchname)
        return [record["name"] for record in result]
    
class Fabric():
    devices = []
    def __init__(self, seed_switch):
        self.devices.append(seed_switch)
        print('Fabric object initialized')

    def list_devices(self):
        print('Listing all the devices in the fabric')
        for index,device in zip(range(1, len(self.devices)+1), self.devices):
            print('Device ', index)
            device.print_details()
            device.print_image()

    def add_device(self, switch):
        if switch.mgmt_ip not in [device.mgmt_ip for device in self.devices]:
            self.devices.append(switch)
            print('Device succeesfully added to Fabric.')
        else:
            print('Device already present in the Fabric.')

    def remove_device(self, switch):
        if switch.mgmt_ip in [device.mgmt_ip for device in self.devices]:
            self.devices.remove(switch)
            print('Device succeesfully removed from Fabric.')
        else:
            print('Device not present in the Fabric.')
            
    def search_devices(self, vsan = 1):
        for device in self.devices:
            if device.password != None:
                stdin, stdout, stderr = device.client.exec_command('show topology vsan {}'.format(vsan))
                extensionsToCheck = ['fc', 'vfc', 'vfc-po', 'san-port-channel', 'port-channel']
                for line in stdout:
                    if any(ext in line for ext in extensionsToCheck):
                        line = line.split()
                        try:
                            peer_ip, switchname = line[3].split('(')
                        except ValueError:
                            print('Getting value error, hence skipping this iteration')
                            continue
                        else:
                            switchname = switchname.rstrip(')')
                            print('PEER IP = {0} SWITCHNAME = {1}'.format(peer_ip, switchname))
                            new_switch = Switch(peer_ip, None, switchname)
                            #new_switch.print_details()
                            self.add_device(new_switch)
            else:
                device.password = ('Please enter device password : ')


class Switch():
    vendor = 'CISCO'
    eth_interface = {}
    fc_interface = {}
    vfc_interface = {}
    sanpo_interface = {}

    def __init__(self, mgmt_ip, password, switchname = None):
        self.mgmt_ip = mgmt_ip
        if password != None:
            self.password = password
        else:
            self.get_password()

        self.client = self.get_client('admin')

        if switchname == None:
            stdin, stdout, stderr = self.client.exec_command('show switchname')
            self.switchname = stdout.readline().strip()
        else:
            self.switchname = switchname

        stdin, stdout, stderr = self.client.exec_command('show inventory')
        self.descr = stdout.readline().split(',')[1].partition(':')[2].strip()

        print('Switch object created with paramiko client in-built.')

    def get_password(self):
        if self.mgmt_ip in device_password_mapping.keys():
            self.password = device_password_mapping[self.mgmt_ip]
            print('Password fetched from provided file.')
        else:
            self.password = input('Please enter device password : ')

    def get_client(self, username):
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(self.mgmt_ip, username = username, password = self.password)
        print('Paramiko client created successfully : ', client)
        return client

    def print_details(self):
        print('Switch Name : ', self.switchname)
        print('Management IP : {0} Password : {1}'.format(self.mgmt_ip, self.password))
        print('Description : ', self.descr)
        print()

    def get_topology(self, vsan = 1):
        peer_connections = []
        cli = 'show topology vsan {}'.format(vsan)
        extensionsToCheck = ['fc', 'vfc', 'vfc-po', 'san-port-channel', 'port-channel']
        stdin, stdout, stderr = self.client.exec_command(cli)
        for line in stdout:
            if any(ext in line for ext in extensionsToCheck):
                line = line.split()
                peer_ip, switchname = line[3].split('(')
                line[3] = peer_ip
                line.append( switchname.rstrip(')') )
                peer_connections.append(line)
        df = pd.DataFrame(peer_connections, columns = ['Interface', 'Peer Domain', 'Peer Interface', 'Peer IP Address', 'Switch Name'])
        return df
        
    def show_topology(self, vsan = 1):
        peer_connections = self.get_topology(vsan)
        print(peer_connections)

    # Returns a pandas dataframe of flogi entries
    def get_flogi_database(self, vsan = 1):
        flogi_database = []
        cli = 'show flogi database vsan {}'.format(vsan)
        stdin, stdout, stderr = self.client.exec_command(cli)
        extensionsToCheck = ['fc', 'vfc', 'vfc-po', 'san-port-channel', 'port-channel']
        for line in stdout:
            if any(ext in line for ext in extensionsToCheck):
                flogi_database.append( line.split() )
        
        df = pd.DataFrame(flogi_database, columns = ['Interface', 'VSAN', 'FCID', 'PORT NAME', 'NODE NAME'])
        return df
    
    def show_flogi_database(self, vsan = 1):
        flogi_database = self.get_flogi_database(vsan)
        print(flogi_database)
        
    def show_int_brief_eth(self, intf = ''):
        print('Fetching eth interfaces...')
        cli = 'show interface {} brief | i eth'.format(intf)
        stdin, stdout, stderr = self.client.exec_command(cli)
        for line in stdout:
            print(line)
            print('Adding eth interfcae : ', line.split())
            name, vlan, type, mode, status, reason, speed, port_channel = line.split()
            eth_intf = EthInterface(self.client, name, vlan, type, mode, status, reason, speed, port_channel)
            self.eth_interface.update({eth_intf.name : eth_intf})
        
    def show_int_brief_fc(self, intf = ''):
        print('Fetching fc interfaces...')
        cli = 'show interface {} brief | i fc | exc vfc'.format(intf)
        stdin, stdout, stderr = self.client.exec_command(cli)
        for line in stdout:
            print(line)
            name, vsan, admin_mode, admin_trunk_mode, status, sfp, oper_mode, oper_speed, port_channel = line.split()
            fc_intf = FcInterface(self.client, name, vsan, admin_mode, admin_trunk_mode, status, sfp, oper_mode, oper_speed, port_channel)
            self.fc_interface.update({fc_intf.name : fc_intf})
          
    def show_int_brief_vfc(self, intf = ''):
        print('Fetching vfc interfaces...')
        cli = 'show interface {} brief | i vfc | exc vfc-po'.format(intf)
        stdin, stdout, stderr = self.client.exec_command(cli)
        for line in stdout:
            print(line)
            name, vsan, admin_mode, admin_trunk_mode, status, bind_info, oper_mode, oper_speed = line.split()
            vfc_intf = VfcInterface(self.client, name, vsan, admin_mode, admin_trunk_mode, status, bind_info, oper_mode, oper_speed)
            self.vfc_interface.update({vfc_intf.name : vfc_intf})
            
    def show_int_brief_sanpo(self, intf = ''):
        print('Fetching san-port-channel interfaces...')
        cli = 'show interface {} brief | i san-port-channel'.format(intf)
        stdin, stdout, stderr = self.client.exec_command(cli)
        for line in stdout:
            print(line)
            try:
                name, vsan, admin_trunk_mode, status, oper_mode, oper_speed, ip_addr = line.split()
            except ValueError:
                print('Getting value error')
            else:
                sanpo_intf = SanPortChannel(self.client, name, vsan, admin_trunk_mode, status, oper_mode, oper_speed, ip_addr)
                self.sanpo_interface.update({sanpo_intf.name : sanpo_intf})
            
    def show_int_brief_vfcpo(self, intf = ''):
        pass

    #Returns a dictionary.
    def get_zoneset_active(self, vsan = 1):
        print('Getting active zoneset info for vsan {}'.format(vsan))
        cli = 'show zoneset active vsan {}'.format(vsan)
        stdin, stdout, stderr = self.client.exec_command(cli)
        zone_data = stdout.readlines()
        zone_data = [line.strip() for line in zone_data]
        #zone_data = [line.strip().strip('*').strip() for line in zone_data]

        zone_dict = dict()
        keywordsToCheck = ['fcid', 'pwwn', 'fwwn', 'fcalias', 'device-alias']

        for line in zone_data:
            if line == '':
                continue
            if line.split()[0] == 'zoneset':
                zoneset_name = line.split()[2]
                print('Active Zoneset : {}'.format(zoneset_name))
            if line.split()[0] == 'zone':
                zone_name = line.split()[2]
                zone_dict[zone_name] = []
            if any(keyword in line.split() for keyword in keywordsToCheck):
                if '*' not in line.split():
                    #Continuing since the member is not online, hence, cannot get the flogi.
                    continue
                else:
                    key = line.split()[1]
                    value = line.split()[2]
                    zone_dict[zone_name].append((key, value))
                
        return zone_dict
        
    def show_zoneset_active(self, vsan = 1):
        zone_dict = self.get_zoneset_active(vsan)
        for key in zone_dict.keys():
            print(key, zone_dict[key])

    # Returns a list of fcns entries
    def get_fcns_database(self, vsan = 1):
        print('Getting fcns database for vsan {}'.format(vsan))
        fcns_entries = []
        cli = 'show fcns database vsan {}'.format(vsan)
        stdin, stdout, stderr = self.client.exec_command(cli)
        fcns_data = stdout.readlines()
        fcns_data = [line.strip() for line in fcns_data]

        regex1 = re.compile(r'0x[0-9a-f]{6}') #Checking for a valid FCID in the line
        regex2 = re.compile(r'\(.*\)') #Checking if Vendor field is present

        for line in fcns_data:
            mo = re.findall(regex1, line)
            if len(mo) == 0 or len(line.split()) == 1:
                #Skipping insignificant lines
                #Ignoring the line since it has only device-alias name
                continue
            else:
                #TODO : Parsing the FCNS database properly
                mo = re.findall(regex2, line)
                if len(mo) == 1:
                    fcid, port_type, pwwn, vendor, *fc4_protocol_feature = line.split()
                    vendor = vendor.lstrip('(').rstrip(')')
                else:
                    fcid, port_type, pwwn, *fc4_protocol_feature = line.split()
                    vendor = None
                
                fc4, protocol = fc4_protocol_feature[0].partition(':')[0].split('-')
                features = fc4_protocol_feature[0].partition(':')[2] + ' ' + ' '.join(x for x in fc4_protocol_feature[1:])
                features = features.split()
                fcns_entries.append((fcid, port_type, pwwn, vendor, fc4, protocol, features))
        
        return fcns_entries

    def show_fcns_database(self, vsan = 1):
        fcns_entries = self.get_fcns_database(vsan)
        for entry in fcns_entries:
            print(entry)

                

    # TODO : Use google search image to get image on runtime
    # Please visit : https://pypi.org/project/Google-Images-Search/
    def print_image(self):
        pass

# Super class, defined to hold common functionalities of an interface.
# Do not use it for instantiation
class Interface:
    def show(self):
        for key, value in self.__dict__.items():
            print(key, value)
    
    def show_brief(self):
        for value in self.__dict__.values():
            print(value, end = ' ')

    def shut(self):
        print('Shutting interface : ', self.name)
        channel = self.client.invoke_shell()
        channel.send('configure terminal \n')
        channel.send('interface {} \n'.format(self.name))
        channel.send('shutdown \n')
        channel.send('exit \n')
        

    def no_shut(self):
        print('Un shuttting interface : ', self.name)
        channel = self.client.invoke_shell()
        channel.send('configure terminal \n')
        channel.send('interface {} \n'.format(self.name))
        channel.send('no shutdown \n')
        channel.send('exit \n')

    def flap(self):
        print('Flapping interface : ', self.name)
        self.shut()
        self.no_shut()


class FcInterface(Interface):
    def __init__(self, client, name, vsan, admin_mode, admin_trunk_mode, status, sfp, oper_mode, oper_speed, port_channel):
        self.client = client
        self.name = name
        self.vsan = vsan
        self.admin_mode = admin_mode
        self.admin_trunk_mode = admin_trunk_mode
        self.status = status
        self.sfp = sfp
        self.oper_mode = oper_mode
        self.oper_speed = oper_speed
        self.port_channel = port_channel

class EthInterface(Interface):
    def __init__(self, client, name, vlan, type, mode, status, reason, speed, port_channel):
        self.client = client
        self.name = name
        self.vlan = vlan
        self.mode = mode
        self.status = status
        self.reason = reason
        self.speed = speed
        self.port_channel = port_channel

class VfcInterface(Interface):
    def __init__(self, client, name, vsan, admin_mode, admin_trunk_mode, status, bind_info, oper_mode, oper_speed):
        self.client = client
        self.name = name
        self.vsan = vsan
        self.admin_mode = admin_mode
        self.admin_trunk_mode = admin_trunk_mode
        self.status = status
        self.bind_info = bind_info
        self.oper_mode = oper_mode
        self.oper_speed = oper_speed

class SanPortChannel(Interface):
    def __init__(self, client, name, vsan, admin_trunk_mode, status, oper_mode, oper_speed, ip_addr):
        self.client = client
        self.name = name
        self.vsan = vsan
        self.admin_trunk_mode = admin_trunk_mode
        self.status = status
        self.oper_mode = oper_mode
        self.oper_speed = oper_speed
        self.ip_addr = ip_addr

class VfcPortChannel(Interface):
    pass

if __name__ == '__main__':
    print('Enter the seed switch details')
    mgmt_ip = input('Enter the management ip : ')
    password = input('Enter the password : ')
    vsan = input('Enter the vsan : ')

    switch = Switch(mgmt_ip, password)
    fabric = Fabric(switch)
    fabric.search_devices()
    fabric.list_devices()

    switch.show_fc_brief()
    switch.show_flogi_database()

    switch.get_fc_interfaces()

    switch.fc_interface[0].flap()
