import paramiko
import pandas as pd

def get_client(ip, username, password):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, username = username, password = password)
    return client

def get_topology(stdout):
    connections = []
    for line in stdout:
        if ('fc' or 'vfc' or 'san-port-channel') in line:
            line = line.split()
            peer_ip, switchname = line[3].split('(')
            line[3:5] = peer_ip, switchname
            line[4] = ''.join(line[4][:len(line[4])-1])
            connections.append(line)
    df = pd.DataFrame(connections, columns = ['Interface', 'Peer Domain', 'Peer Interface', 'Peer IP Address', 'Switch Name'])
    return df


def get_flogi_database(stdout):
    database = []
    for line in stdout:
        if ('fc' or 'vfc') in line :
            database.append(line.split())
    df = pd.DataFrame(database, columns = ['Interface', 'VSAN', 'FCID', 'PORT NAME', 'NODE NAME'])
    return df

"""
Extra cases to be covered
1. what if the output of the cmd is empty?
2. cover the case when switchname is of single word.
3. inti/target info along with fcid for flogi(s).
"""
