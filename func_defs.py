import paramiko
import pandas as pd
import re

def get_client(ip, username, password):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, username = username, password = password)
    return client

def get_switch_info(stdout):
    switch_info = stdout.readline()
    return switch_info

def get_swtich_name(stdout):
    switch_name = stdout.readline()
    return switch_name

def get_fc_interface_brief(stdout, switch_info):
    interface_info = []
    for line in stdout:
        if 'vfc' not in line:
            line = line.split()
            interface_info.append(line)
    if 'MDS' in switch_info:
        df = pd.DataFrame(interface_info, columns =['Interface', 'VSAN', 'Admin Mode', 'Admin Trunk Mode', 
                                                'Status', 'SFP', 'Oper Mode', 'Oper Speed (Gbps)', 
                                                'Port Channel', 'Logical Type'])
    else:
        df = pd.DataFrame(interface_info, columns =['Interface', 'VSAN', 'Admin Mode', 'Admin Trunk Mode', 
                                                'Status', 'SFP', 'Oper Mode', 'Oper Speed (Gbps)', 
                                                'Port Channel'])
    return df

def get_san_po_interface_brief(stdout, switch_info):
    interface_info = []
    for line in stdout:
        line = line.split()
        if len(line) == 6:
            line.append('--')
        interface_info.append(line)
    
    if 'MDS' in switch_info:
        df = pd.DataFrame(interface_info, columns =['Interface', 'VSAN', 'Admin Trunk Mode', 
                                                'Status', 'Oper Mode', 'Oper Speed (Gbps)', 
                                                'IP Address', 'Logical Type'])
    else:
        df = pd.DataFrame(interface_info, columns =['Interface', 'VSAN', 'Admin Trunk Mode', 
                                                'Status', 'Oper Mode', 'Oper Speed (Gbps)', 
                                                'IP Address'])

    return df

def get_interface_info(stdout):
    line = stdout.readline()
    return line
    #match = re.findall(r"\[\D*\]", line)

def print_port_internal_errors(client, intf):
    print('\nPrinting port internal errors  for interface ' + intf)
    cmd = 'show port internal info interface {0} | grep Vsan'.format(intf)
    __, stdout, __ = client.exec_command(cmd)
    flag = 0
    for line in stdout:
        if '(up)' not in line:
            flag = 1
            print(line, end = '')
    return flag

def activate_port_license(client, intf):
    print('\nActivating port license for interface ' + intf)
    client.exec_command('interface ' + intf)
    client.exec_command('shutdown')
    pass

def flap_port(client, intf):
    print('Flapping interface ' + intf)
    client.exec_command('interface ' + intf)
    client.exec_command('shutdown')
    client.exec_command('no shutdown')

def get_topology(stdout):
    connections = []
    extensionsToCheck = ['fc', 'vfc', 'vfc-po', 'san-port-channel', 'port-channel']
    for line in stdout:
        if any(ext in line for ext in extensionsToCheck):
            line = line.split()
            peer_ip, switchname = line[3].split('(')
            line[3] = peer_ip
            line.append( switchname.rstrip(')') )
            connections.append(line)
    df = pd.DataFrame(connections, columns = ['Interface', 'Peer Domain', 'Peer Interface', 'Peer IP Address', 'Switch Name'])
    return df


def get_flogi_database(stdout):
    database = []
    extensionsToCheck = ['fc', 'vfc', 'vfc-po', 'san-port-channel', 'port-channel']
    for line in stdout:
        if any(ext in line for ext in extensionsToCheck):
            database.append( line.split() )
    df = pd.DataFrame(database, columns = ['Interface', 'VSAN', 'FCID', 'PORT NAME', 'NODE NAME'])
    return df

def get_fcns_database(stdout):
    database = []
    regex1 = re.compile(r'0x[0-9a-f]{6}') #Checking if it is the significant line to drop device-alias rows
    regex2 = re.compile(r'\(.*\)') #Checking if Vendor field is present
    for line in stdout:
        mo = re.findall(regex1, line)
        if len(mo) >= 1:
            line = line.split()
            mo = re.fullmatch(regex2, line[3])
            if mo == None:
                line.insert(3, '--')
            if len(line) == 5:
                line.append('--')
            database.append(line)
    df = pd.DataFrame(database, columns = ['FCID', 'TYPE', 'PWWN', '(VENDOR)', 'FC4-TYPE', 'FEATURE'])
    return df

"""
Extra cases to be covered
1. what if the output of the cmd is empty?
2. cover the case when switchname is of single word.
3. init/target info along with fcid for flogi(s).
"""
