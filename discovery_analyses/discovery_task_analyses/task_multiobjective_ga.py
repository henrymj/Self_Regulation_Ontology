"""
assess the ability to reconstruct data from a subset of variables
use combination of subject correlation and reconstruction objectives
"""


import os,glob,sys,itertools,time,pickle
import numpy,pandas
import json
from sklearn.preprocessing import scale

from search_objectives import get_subset_corr,get_reconstruction_error

if len(sys.argv)>1:
   clf=sys.argv[1]
   print('using ',clf)
else:
    clf='linear'

if len(sys.argv)>2:
   nsplits=int(sys.argv[2])
   print('nsplits=',nsplits)
else:
    nsplits=4

num_cores=2
#num_cores = multiprocessing.cpu_count()
print('using %d cores'%num_cores)


# this is kludgey but it works
sys.path.append('../utils')
from utils import get_info,get_behav_data

dataset=get_info('dataset')
print('using dataset:',dataset)
basedir=get_info('base_directory')
derived_dir=os.path.join(basedir,'Data/Derived_Data/%s'%dataset)


data=pandas.read_csv(os.path.join(derived_dir,'taskdata_clean_cutoff3.00IQR_imputed.csv'))

cdata=scale(data.values)
nsubs=data.shape[0]
subcorr=numpy.corrcoef(cdata)[numpy.triu_indices(nsubs,1)]

# get task names and indicator
tasknames=[i.split('.')[0] for i in data.columns]
tasks=list(set(tasknames))
tasks.sort()

ntasks=8 # number of tasks to select - later include time

tasknums=[i for i in range(len(tasks))]



# set up genetic algorithm


def get_initial_population(popsize,allcombs):
    numpy.random.shuffle(allcombs)
    poplist=[list(i) for i in allcombs[:popsize]]
    return(poplist)

def get_population_fitness(pop,data,nsplits,clf,obj_weight=[0.5,0.5]):
    # first get cc for each item in population
    cc_recon=[get_reconstruction_error(ct,data,nsplits,clf) for ct in pop]
    cc_subsim=[get_subset_corr(ct,data) for ct in pop]
    cc_recon=scale(cc_recon)
    cc_subsim=scale(cc_subsim)
    cc=cc_recon*obj_weight[0] + cc_subsim*obj_weight[1]
    return cc

def select_parents(pop,data,nsel,clf,nsplits=4):
    cc=get_population_fitness(pop,data,nsplits,clf)
    idx=numpy.argsort(cc)[::-1]
    pop_sorted=[pop[i] for i in idx[:nsel]]
    cc_sorted=[cc[i] for i in idx[:nsel]]
    return(pop_sorted,cc_sorted)

def crossover(pop,assortative_mating=False,nbabies=2):
    # assortative mating - best parents mate
    families=numpy.kron(numpy.arange(numpy.floor(len(pop)/2)),[1,1])
    if not assortative_mating:
        numpy.random.shuffle(families)
    for f in numpy.unique(families):
        famidx=[i for i in range(len(families)) if families[i]==f]
        if len(famidx)!=2:
            continue
        try:
            subpop=[pop[i] for i in famidx]
        except:
            print('oops...')
            print(len(pop))
            print(famidx)
            raise Exception('breaking')
        parents=list(set(subpop[0] + subpop[1]))
        if len(set(parents))<len(subpop[1]):
            continue
        for b in range(nbabies):
            numpy.random.shuffle(parents)
            baby=parents[:len(subpop[1])]
            pop.append(baby)
    return pop

def immigrate(pop,allcombs,n):
    immigrants=[list(allcombs[i]) for i in numpy.random.randint(len(allcombs),size=n)]
    return pop+immigrants

def mutate(pop,mutation_rate):
    mutants=numpy.random.randint(len(pop),size=numpy.round(mutation_rate*len(pop)))
    for m in mutants:
        alts=[i for i in range(len(tasks)) if not i in pop[m]]
        numpy.random.shuffle(alts)
        mutpos=numpy.random.randint(len(pop[m]))
        #print(pop[m],mutpos)
        pop[m][mutpos]=alts[0]
        #print(pop[m])
    return pop,mutants

try:
    allcombs
except:
    allcombs=[i for i in itertools.combinations(range(32),8)]

start_time = time.time()
population=get_initial_population(1000,allcombs)
ngen=250
mutation_rate=0.01
ccmax=numpy.zeros(ngen)
bestp_saved={}
bestctr=0
clf='kridge'

for generation in range(ngen):
    population,cc=select_parents(population,data,100,clf)
    ccmax[generation]=numpy.max(cc)
    bestp=population[numpy.where(cc==ccmax[generation])[0][0]]
    bestp.sort()
    bestp_saved[generation]=bestp
    if generation>1 and bestp_saved[generation]==bestp_saved[generation-1]:
        bestctr+=1
    else:
        bestctr=0
    for i in bestp:
        print(i,tasks[i])
    print(bestp)
    if bestctr>9:
        break
    population=crossover(population)
    population=immigrate(population,allcombs,1000)
    population,mutants=mutate(population, mutation_rate)
    print(generation,ccmax[generation])


population,cc=select_parents(population,data,100,clf)
bestp=population[numpy.where(cc==numpy.max(cc))[0][0]]
bestp_saved[generation+1]=bestp
ccmax[generation+1]=numpy.max(cc)
ccmax=ccmax[:generation+2]
bestp.sort()
for i in bestp:
    print(i,tasks[i])

print('Time elapsed (secs):', time.time()-start_time)

pickle.dump((bestp_saved,ccmax),open("multiobj_results_%s.pkl"%clf,'wb'))

#numpy.save('reconstruction_%s_cc.npy'%clf,cc)
#numpy.save('reconstruction_%s_sse.npy'%clf,sse)
