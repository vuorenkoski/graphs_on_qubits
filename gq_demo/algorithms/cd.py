from django.shortcuts import render

import numpy as np
from dimod import BinaryQuadraticModel
import networkx as nx
import numpy as np

from gq_demo.graphs import create_graph
from gq_demo.utils import basic_stats, solve, graph_to_json, Q_to_json, colors, algorithms, graph_types

min_vertices = 5
max_vertices = 60
min_communities = 1
max_communities = 10
max_num_reads = 10000
solvers = ['local simulator', 'cloud hybrid solver', 'Advantage_system4.1', 'Advantage_system5.4', 'Advantage_system6.4']

def index(request):
    resp = {}
    resp['algorithm'] = 'Community detection'
    resp['correctness'] = 'Community graphs have three artificial communities. The accuracy is measured by the difference of modularity value of the '\
         'outcome (lowest energy level produced) and the modularity value of outcome of calssical NetworkX function greedy_modularity_communities.'\
         ' More positive this value is, more poorer the modularity of the algorithms outcome was.'
    resp['algorithms'] = algorithms
    resp['solvers'] = solvers
    resp['graph_types'] = graph_types
    resp['min_vertices'] = min_vertices
    resp['max_vertices'] = max_vertices
    resp['min_communities'] = min_communities
    resp['max_communities'] = max_communities
    resp['max_num_reads'] = max_num_reads
    if request.method == "POST":
        # Get parameters
        resp['vertices'] = int(request.POST['vertices'])
        resp['num_reads'] = int(request.POST['num_reads'])
        resp['solver'] = request.POST['solver']
        resp['structure'] = request.POST['structure']
        resp['token'] = request.POST['token']
        resp['graph_type'] = request.POST['graph_type']
        resp['communities'] = int(request.POST['communities'])

        # Check validity
        if resp['vertices']<min_vertices or resp['vertices']>max_vertices:
            resp['error'] = 'vertices must be '+str(min_vertices)+'..'+str(max_vertices)
            return render(request, 'cd/index.html', resp) 

        if resp['communities']<min_communities or resp['communities']>max_communities:
            resp['error'] = 'communities must be '+str(min_communities)+'..'+str(max_communities)
            return render(request, 'cd/index.html', resp) 

        if resp['num_reads']>max_num_reads:
            resp['error'] = 'Maximum number fo reads is '+str(max_num_reads)
            return render(request, 'cd/index.html', resp) 

        # create graph, qubo, bqm
        try:
            G = create_graph(resp['graph_type'], resp['vertices'], resp['structure'], weight=True, directed=False)
            Q, offset = create_qubo_cd(G, resp['communities'])
            bqm = create_bqm_cd(Q, offset, G, resp['communities'])
            result = basic_stats(G,Q, bqm)
        except Exception as err:
            resp['error'] = 'error in graph structure'
            return render(request, 'algorithm.html', resp) 

        # Solve
        try:
            r, sampleset = solve(bqm,resp)
            result.update(r)
        except Exception as err:
            resp['error'] = err
            return render(request, 'algorithm.html', resp) 

        # Gather rest of results
        resp['qdata'] = {'data': Q_to_json(Q.tolist()), 'size':len(Q)}
        result['success'] = check_result_cd(G,sampleset,resp['communities'])
        resp['result'] = result

        # Create graph-data
        resp['gdata'] = {'data': graph_to_json(G), 'colors': result_to_colors(G, sampleset.first.sample), 'directed':0, 'weights':1}
    else:
        # These are initial parameters for web page
        resp['vertices'] = 7
        resp['num_reads'] = 2000
        resp['solver'] = 'local simulator'
        resp['structure'] = ''
        resp['token'] = ''
        resp['graph_type'] = 'community graph'
        resp['communities'] = 4
    return render(request, 'algorithm.html', resp) 

def create_bqm_cd(Q, offset, G, communities):
    labels = {}
    for i in range(len(G.nodes)):
        for j in range(communities):
            labels[i*communities + j]=(i,j)
    return BinaryQuadraticModel.from_qubo(Q, offset = offset).relabel_variables(labels, inplace=False)

def result_to_colors(G, sample):
    cs = np.zeros(len(G.nodes))
    for k,v in sample.items():
        if v==1: 
            cs[k[0]]=k[1]+1
    nc = []
    for i in range(len(cs)):
        nc.append(colors[int(cs[i])])
    return nc

def create_qubo_cd(G, communities):
    vertices = len(G.nodes)
    Q = np.zeros((vertices*communities, vertices*communities))
    offset = 0

    p = 0.1
    # Vertex must belong to exactly one community
    for c in range(communities): 
        for v in range(vertices):
            Q[v*communities+c,v*communities+c] -= p
            for k in range(1, communities-c):
                Q[v*communities+c,v*communities+c+k] += 2 * p
    offset += vertices * p
    
    # Minimise modularity
    m = 0
    for e in G.edges:
        m += G[e[0]][e[1]]['weight']

    k = np.zeros(vertices)
    for e in G.edges:
        k[e[0]] += G[e[0]][e[1]]['weight']
        k[e[1]] += G[e[0]][e[1]]['weight']

    w = np.zeros((vertices,vertices))
    for e in G.edges:
        w[e[0],e[1]] = G[e[0]][e[1]]['weight']
        w[e[1],e[0]] = w[e[0],e[1]]
    
    for c in range(communities):
        for i in range(vertices): 
            for j in range(vertices): 
                Q[i*communities+c, j*communities+c] += (k[i] * k[j] / (2 * m) - w[i,j]) / (2 * m)
    return Q, offset

def check_result_cd(G, sampleset, communities):
    c1 = nx.community.greedy_modularity_communities(G, weight='weight', best_n=communities)
    return str(abs(round(nx.community.modularity(G,c1) + sampleset.first.energy,3)))