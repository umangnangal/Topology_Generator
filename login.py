import paramiko
import pandas as pd
from func_defs import *

#Setting pandas config
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', -1)

switch_database = []

print('----------- Enter the seed switch details -----------')
mgmt_ip = input('Enter the management ip : ')
password = input('Enter the password : ')
vsan = input('Enter the vsan : ')

switch_database.append(['', mgmt_ip, password, 0])
flag = 1

while flag:
    for item in switch_database:
        if item[3] == 1:
            continue
        else:
            mgmt_ip = item[1]
            password = item[2]
            rc = 0
            count = 0
            while count < 2 :
                try:
                    client = get_client(mgmt_ip, 'admin', password)
                    item[2] = password
                    if item[0] == '':
                        stdin, stdout, stderr = client.exec_command('show switchname')
                        item[0] = stdout.readline().strip()
                    rc = 1
                    item[3] = 1
                    count = 2
                except paramiko.ssh_exception.AuthenticationException:
                    print('Authentication Failure')
                    count = count + 1
                    print("Retrying...[{0}] ".format(count))
                    password = input('Please neter the password again for {0}'.format(mgmt_ip))
                    item[2] = ''
                    item[3] = 'Retry limit reached [2]'
            if rc:
                cmd = 'show topology vsan ' + vsan
                stdin, stdout, stderr = client.exec_command(cmd)
                df1 = get_topology(stdout)
                print(df1)
                for i in range(df1.shape[0]):
                    if df1['Switch Name'][i] not in [ x[0] for x in switch_database ]:
                        switch_database.append([ df1['Switch Name'][i], df1['Peer IP Address'][i], input('Enter the password for {0} : '.format(df1['Switch Name'][i])), 0 ])
                        print('Switch info stored successfully')
                print(switch_database)
                client.close()
    flag = 0
    for item in switch_database:
        if item[3] == 0:
            flag = 1
    if flag == 0:
        break

df = pd.DataFrame(switch_database, columns = ['Name', 'Mgmt IP', 'Password', 'Visited?'])
print(df)

import matplotlib.pyplot as plt
from graphviz import Graph,render
import tempfile
G = Graph(name='Network Topology for vsan ' + vsan, node_attr={'shape': 'box'})

for i in range(df.shape[0]):
    print('Entered in switch : ', df['Name'][i])
    if df['Password'][i].strip():
        client = get_client(df['Mgmt IP'][i], 'admin', df['Password'][i])
        cmd = 'show topology vsan ' + vsan
        stdin, stdout, stderr = client.exec_command(cmd)
        df1 = get_topology(stdout)
        print(df1)
        G.node(df['Name'][i])
        for j in range(df1.shape[0]):
            G.node(df1['Switch Name'][j])
            tail = df1['Switch Name'][j]
            if len(tail.split('-' or '_')) > 1:
                tail = '"' + df1['Switch Name'][j] + '"'
            head = df['Name'][i]
            if len(head.split('-' or '_')) > 1:
                head = '"' + df['Name'][i] + '"'
            label = tail + ' -- ' + head + ' [headlabel="{0}" labelfontsize=4 taillabel="{1}"]'.format(df1['Interface'][j], df1['Peer Interface'][j])
            print('checking if this link already exists ....... ',label)
            if label not in [x.strip() for x in G.body]:
                G.edge( df['Name'][i], df1['Switch Name'][j], headlabel=df1['Peer Interface'][j], taillabel=df1['Interface'][j], labelfontsize="4" )
            else:
                print('redundant link found, no need to add it')
        
        cmd = 'show flogi database vsan ' + vsan
        stdin, stdout, stderr = client.exec_command(cmd)
        df1 = get_flogi_database(stdout)
        print(df1)

        cmd = 'show fcns database vsan ' + vsan
        stdin, stdout, stderr = client.exec_command(cmd)
        df2 = get_fcns_database(stdout)
        df2 = df2.set_index('FCID')
        print(df2)
        
        for j in range(df1.shape[0]):
            fc4_type = df2['FC4-TYPE'][df1['FCID'][j]].replace(':','-')
            node_name = df1['FCID'][j] + '\n' + fc4_type
            G.node(node_name, _attributes={'shape':'oval'})
            G.edge(df['Name'][i], node_name, taillabel=df1['Interface'][j], labelfontsize="4")
        
        client.close()
        
#G.attr(label='Network Topology for vsan ' + vsan)
print(G.body)
G.render(view = True)
#G.view(tempfile.mktemp('.gv')) 


