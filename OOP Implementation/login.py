import paramiko
import pandas as pd
import os
from func_defs import *

#Setting pandas config
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', -1)

switch_database = []

class Switch():
    vendor = 'CISCO'
    def __init__(self, mgmt_ip, password):
        self.mgmt_ip = mgmt_ip
        self.password = password
        self.client = self.get_client('admin')

        stdin, stdout, stderr = self.client.exec_command('show switchname')
        self.switchname = stdout.readline().strip()

        stdin, stdout, stderr = self.client.exec_command('show inventory')
        self.descr = stdout.readline().split(',')[1].partition(':')[2].strip()

        print('Switch object created with paramiko client in-built.')
        
    def get_client(self, username):
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(self.mgmt_ip, username = username, password = self.password)
        print('Paramiko client created successfully.')
        return client

    def print_details(self):
        print('Switch Name : ', self.switchname)
        print('Management IP : ', self.mgmt_ip)
        print('Description : ', self.descr)

    def show_fc_brief(self):
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


print('----------- Enter the seed switch details -----------')
mgmt_ip = input('Enter the management ip : ')
password = input('Enter the password : ')
vsan = input('Enter the vsan : ')

switch = Switch(mgmt_ip, password)
switch.print_details()
switch.show_fc_brief()