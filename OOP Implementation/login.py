import paramiko
import pandas as pd
import os
from func_defs import *


#Setting pandas config
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', -1)

#Fetching passwords from user-provided excel sheet and storing it in a dictionary
if os.path.isfile('device_password_mapping.xlsx'):
    df = pd.read_excel('device_password_mapping.xlsx')
    print(df)
    device_password_mapping = dict()
    for i in range(df.shape[0]):
        device_password_mapping[df['Management IP'][i]] = df['Password'][i]
    print(device_password_mapping)
else:
    print("Please create file 'device_password_mapping.xlsx' with Switchname and Password as Header.")

class Fabric():
    devices = []
    def __init__(self, seed_switch):
        self.devices.append(seed_switch)
        print('''
==========================
Fabric object initialized
==========================
''')

    def list_devices(self):
        print('''
=======================================
Listing all the devices in the fabric :
=======================================
        ''')
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

    def search_devices(self):
        for device in self.devices:
            if device.password != None:
                stdin, stdout, stderr = device.client.exec_command('show topology vsan 1')
                extensionsToCheck = ['fc', 'vfc', 'vfc-po', 'san-port-channel', 'port-channel']
                for line in stdout:
                    if any(ext in line for ext in extensionsToCheck):
                        line = line.split()
                        peer_ip, switchname = line[3].split('(')
                        switchname = switchname.rstrip(')')
                        print('PEER IP = {0} SWITCHNAME = {1}'.format(peer_ip, switchname))
                        new_switch = Switch(peer_ip, None, switchname)
                        #new_switch.print_details()
                        self.add_device(new_switch)
            else:
                device.password = ('Please enter device password : ')
    
    def show_toplogy(self):
        pass


class Switch():
    vendor = 'CISCO'
    eth_interface = []
    fc_interface = []

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
        print('Paramiko client created successfully.')
        return client

    def print_details(self):
        print('Switch Name : ', self.switchname)
        print('Management IP : {0} Password : {1}'.format(self.mgmt_ip, self.password))
        print('Description : ', self.descr)
        print()

    def show_fc_brief(self):
        print('Interface Details :')
        stdin, stdout, stderr = self.client.exec_command('show interface brief')
        interface_info = []
        for line in stdout:
            if 'fc' in line and 'vfc' not in line:
                line = line.split()
                interface_info.append(line)
        df = pd.DataFrame(interface_info, columns =['Interface', 'VSAN', 'Admin Mode', 'Admin Trunk Mode', 
                                                    'Status', 'SFP', 'Oper Mode', 'Oper Speed (Gbps)', 
                                                    'Port Channel'])
        print(df)

    def show_flogi_database(self):
        print('Flogi Database : ')
        stdin, stdout, stderr = self.client.exec_command('show flogi database')
        flogi_database = []
        extensionsToCheck = ['fc', 'vfc', 'vfc-po', 'san-port-channel', 'port-channel']
        for line in stdout:
            if any(ext in line for ext in extensionsToCheck):
                flogi_database.append( line.split() )
        df = pd.DataFrame(flogi_database, columns = ['Interface', 'VSAN', 'FCID', 'PORT NAME', 'NODE NAME'])
        print(df)

    def get_fc_interfaces(self):
        print('Fetching fc interfaces...')
        stdin, stdout, stderr = self.client.exec_command('show interface brief | i fc')
        for line in stdout:
            print('Adding fc interface : ', line.split())
            name, vsan, admin_mode, admin_trunk_mode, status, sfp, oper_mode, oper_speed, port_channel = line.split()
            fc_intf = FcInterface(self.client, name, vsan, admin_mode, admin_trunk_mode, status, sfp, oper_mode, oper_speed, port_channel)
            self.fc_interface.append(fc_intf)

    def get_eth_interfaces(self):
        print('Fetching eth interfaces...')
        stdin, stdout, stderr = self.client.exec_command('show interface brief | i eth')
        for line in stdout:
            print('Adding eth interfcae : ', line.split())
            name, vlan, type, mode, status, reason, speed, port_channel = line.split()
            eth_intf = EthInterface(self.client, name, vlan, type, mode, status, reason, speed, port_channel)
            self.eth_interface.append(eth_intf)



    #TODO : Use google search image to get image on runtime
    #Please visit : https://pypi.org/project/Google-Images-Search/
    def print_image(self):
        pass

class Interface:
    pass



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

    def shut(self):
        print('Shutting interface : ', self.name)
        self.client.exec_command('interface {}'.format(self.name))
        self.client.exec_command('shutdown')

    def no_shut(self):
        print('Un shuttting interface : ', self.name)
        self.client.exec_command('interface {}'.format(self.name))
        self.client.exec_command('no shutdown')

    def flap(self):
        print('Flapping interface : ', self.name)
        self.shut()
        self.no_shut()

class EthInterface(Interface):
    pass

class VfcInterface(Interface):
    pass

class SanPortChannel(Interface):
    pass

class VfcPortChannel(Interface):
    pass

if __name__ == '__main__':
    print('''
    ==============================
    Enter the seed switch details 
    ==============================
    ''')
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
