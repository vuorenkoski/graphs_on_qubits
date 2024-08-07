from django.shortcuts import render

from dimod import BinaryQuadraticModel
import numpy as np

from gq_demo.graphs import create_graph
from gq_demo.utils import basic_stats, solve, graph_to_json, graph_to_json, Q_to_json, colors, algorithms, graph_types

min_vertices = 5
max_vertices = 20
max_num_reads = 10000
solvers = ['local simulator', 'cloud hybrid solver', 'Advantage_system4.1', 'Advantage_system5.4', 'Advantage_system6.4']

def index(request):
    resp = {}
    resp['algorithm'] = 'Graph isomorphism'
    resp['correctness'] = 'The algorithm is tested with the defined graph and the same graph having its vertices randomly permutated. '\
    'When working correctly, result should indicate that the graphs are isomorphic. The accuracy is measured by how much observed '\
    'energy level differed from the correct energy level. So, for correct outcome this is 0. More positive '\
    'this indicator is, more far away achieved energy level is from the correct energy level.'
    resp['algorithms'] = algorithms
    resp['solvers'] = solvers
    resp['graph_types'] = graph_types
    resp['min_vertices'] = min_vertices
    resp['max_vertices'] = max_vertices
    resp['max_num_reads'] = max_num_reads
    if request.method == "POST":
        # Get parameters
        resp['vertices'] = int(request.POST['vertices'])
        resp['num_reads'] = int(request.POST['num_reads'])
        resp['solver'] = request.POST['solver']
        resp['structure'] = request.POST['structure']
        resp['token'] = request.POST['token']
        resp['graph_type'] = request.POST['graph_type']

        # Check validity
        if resp['vertices']<min_vertices or resp['vertices']>max_vertices:
            resp['error'] = 'vertices must be '+str(min_vertices)+'..'+str(max_vertices)
            return render(request, 'gi/index.html', resp) 

        if resp['num_reads']>max_num_reads:
            resp['error'] = 'Maximum number fo reads is '+str(max_num_reads)
            return render(request, 'gi/index.html', resp) 

        # create graph, qubo, bqm
        try:
            G1, G2 = create_graph(resp['graph_type'], resp['vertices'], resp['structure'], weight=False, directed=False, permutation=True)
            Q, offset = create_qubo_gi(G1,G2)
            bqm = create_bqm_gi(Q, offset, G1)
            result = basic_stats(G1, Q, bqm)
            exp_energy = -result['edges']
            result['exp_energy'] = str(exp_energy)
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
        result['energy'] = str(sampleset.first.energy)
        result['success'] = str(round(sampleset.first.energy - exp_energy,3))
        result['result'] = check_result_gi(sampleset, exp_energy, result['vertices'])
        resp['result'] = result

        # Create graph-data
        resp['gdata'] = {'data': graph_to_json(G1), 'colors': [colors[0] for i in range(len(G1.nodes))], 'directed':0, 'weights':0}

    else:
        # These are initial parameters for web page
        resp['vertices'] = 7
        resp['num_reads'] = 2000
        resp['solver'] = 'local simulator'
        resp['structure'] = ''
        resp['token'] = ''
        resp['graph_type'] = 'wheel graph'
    return render(request, 'algorithm.html', resp) 

def create_bqm_gi(Q, offset, G):
    labels = {}
    vertices = len(G.nodes)
    for i in range(vertices):
        for j in range(vertices):
            labels[i*vertices+j] = (i,j)
    return BinaryQuadraticModel.from_qubo(Q, offset = offset).relabel_variables(labels, inplace=False)

def create_qubo_gi(G1, G2):
    vertices = len(G1.nodes)
    E1 = [] 
    for e in G1.edges(data=True):
        E1.append((e[0],e[1]))
    E2 = [] 
    for e in G2.edges(data=True):
        E2.append((e[0],e[1]))
    Q = np.zeros((vertices*vertices, vertices*vertices))
    offset = 0
    
    p = vertices 
    # Bijectivity 1
    for v1 in range(vertices):
        for v2 in range(vertices): 
            Q[v1*vertices+v2,v1*vertices+v2] -= p 
            for k in range(1,vertices-v2): 
                Q[v1*vertices+v2,v1*vertices+v2+k] += 2 * p 
    offset += vertices * p

    # Bijectivity 2
    for v2 in range(vertices):
        for v1 in range(vertices): 
            Q[v2*vertices+v1,v2*vertices+v1] -= p 
            for k in range(1,vertices-v1): 
                Q[v1*vertices+v2,(v1+k)*vertices+v2] += 2 * p
    offset += vertices * p

    # Mapping respects edges 
    for (v1,v2) in E1: 
        for (w1,w2) in E2: 
            Q[v1*vertices+w1, v2*vertices+w2] -= 1
            Q[v1*vertices+w2, v2*vertices+w1] -= 1

    # All quadratic coefficients in lower triangle to upper triangle
    for i in range(vertices*vertices): 
        for j in range(i):
            Q[j,i] += Q[i,j]
            Q[i,j] = 0

    return Q, offset

def check_result_gi(sampleset, e, v):
    sample = sampleset.first.sample
    n = 0
    mapping = {}
    for x in sample.keys():
        if sample[x]==1:
            mapping[x] = 1
            n += 1

    if n!=v:
        return 'bijection error'
    vi=0
    vj=0
    for i in range(v):
        for j in range(v):
            if (i,j) in mapping.keys():
                vi += 1
                vj += 1
    if vi!=v or vj!=v:
        return 'bijection error'
    
    if int(sampleset.first.energy)==e:
        return 'isomorphic'
    else:
        return 'non-isomorphic'
    
