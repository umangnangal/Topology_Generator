import paramiko
import pandas as pd
import re

def get_client(ip, username, password):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, username = username, password = password)
    return client

def get_topology(stdout):
    connections = []
    extensionsToCheck = ['fc', 'vfc', 'san-port-channel', 'port-channel']
    for line in stdout:
        if any(ext in line for ext in extensionsToCheck):
            line = line.split()
            peer_ip, switchname = line[3].split('(')
            line[3:5] = peer_ip, switchname
            line[4] = ''.join(line[4][:len(line[4])-1])
            connections.append(line)
    df = pd.DataFrame(connections, columns = ['Interface', 'Peer Domain', 'Peer Interface', 'Peer IP Address', 'Switch Name'])
    return df


def get_flogi_database(stdout):
    database = []
    extensionsToCheck = ['fc', 'vfc', 'san-port-channel', 'port-channel']
    for line in stdout:
        if any(ext in line for ext in extensionsToCheck):
            database.append(line.split())
    df = pd.DataFrame(database, columns = ['Interface', 'VSAN', 'FCID', 'PORT NAME', 'NODE NAME'])
    return df

def get_fcns_database(stdout):
    database = []
    regex = re.compile(r'0x[0-9]{6}')
    for line in stdout:
        mo = re.findall(regex, line)
        if len(mo) >= 1:
            database.append(line.split())
    df = pd.DataFrame(database, columns = ['FCID', 'Type', 'PWWN', 'Vendor', 'FC4-TYPE'])
    return df

"""
Extra cases to be covered
1. what if the output of the cmd is empty?
2. cover the case when switchname is of single word.
3. inti/target info along with fcid for flogi(s).
"""
