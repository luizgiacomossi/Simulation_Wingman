import numpy as np
import random
from math import inf
import copy # utilizar deepcopy para copiar objeto 

class Particle:
    """
    Represents a particle of the Particle Swarm Optimization algorithm.
    """
    def __init__(self, lower_bound, upper_bound):
        """
        Creates a particle of the Particle Swarm Optimization algorithm.

        :param lower_bound: lower bound of the particle position.
        :type lower_bound: numpy array.
        :param upper_bound: upper bound of the particle position.
        :type upper_bound: numpy array.
        """
        # Todo: implement
        # Particula é candidato á solução

        self.delta = upper_bound - lower_bound
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        # Gera posição dentro dos limites passados
        self.position = np.random.uniform(low = lower_bound, high = upper_bound)
        self.best = self.position # melhor posicao da particula é a inicial
        # Gera velocidade dentro dos limites passados (delta)
        self.velocity = np.random.uniform(low = - self.delta , high = self.delta)
        self.best_cost = -inf # maximization

class ParticleSwarmOptimization:
    """
    Represents the Particle Swarm Optimization algorithm.
    Hyperparameters:
        w     : inertia_weight      : inertia weight.
        phi p : cognitive_parameter : cognitive parameter.
        phi g : social_parameter    : social parameter.

    :param hyperparams: hyperparameters used by Particle Swarm Optimization.
    :type hyperparams: Params.
    :param lower_bound: lower bound of particle position.
    :type lower_bound: numpy array.
    :param upper_bound: upper bound of particle position.
    :type upper_bound: numpy array.
    """
    def __init__(self, hyperparams, lower_bound, upper_bound):
        # Todo: implement
        # Armazena hiperparametros e 
        # limites para inicilizar particulas
        self.hyperparams = hyperparams
        self.lower = lower_bound
        self.upper = upper_bound

        # cria N particulas dentro dos limites 
        self.particles = self.initialize_particles(self.lower, self.upper, 
        hyperparams.num_particles )

        # auxiliares para contagem de iteraçoes/geracoes 
        self.iteration = 0 # para get_position_to_evaluate
        self.count_generations = 0 # Contagem de geracoes

        # Armazena Melhor global e seu custo
        self.best_global = None 
        self.best_quality_global = -inf

        # variavel auxiliar para armazenar melhor custo da geracao
        # iniciliza-se para primeira iteração como -inf (p/ maximizacao)
        self.best_cost_generation = []
        self.best_cost_generation.append(-inf)


    # Metodo auxiliar para criar particulas 
    def initialize_particles(self,lower_bound, upper_bound, num_particles):
        """
        Method for Creating N particles 

        :return: N particles.
        :rtype: list of objects Particles.
        """
        # armazena particulas
        particles = []
        # loop para criar n particulas desejadas dentro dos limites passados
        for i in range(num_particles):
            # Cria particula
            particle = Particle( lower_bound, upper_bound)
            # Adiciona a lista de particulas
            particles.append( particle )
            
        return particles

    def get_best_position(self):
        """
        Obtains the best position so far found by the algorithm.

        :return: the best position.
        :rtype: numpy array.
        """
        # Todo: implement

        # Obtem posicao do melhor avaliado
        return self.best_global.position

    def get_best_value(self):
        """
        Obtains the value of the best position so far found by the algorithm.

        :return: value of the best position.
        :rtype: float.
        """
        # Todo: implement
        return self.best_quality_global 

    def get_position_to_evaluate(self):
        """
        Obtains a new position to evaluate.

        :return: position to evaluate.
        :rtype: numpy array.
        """
        # Todo: implement
        aux= self.particles[ self.iteration ]

        return aux.position

    def advance_generation(self):
        """
        Advances the generation of particles. Auxiliary method 
        to be used by notify_evaluation().
        """
        # Todo: implement
        # Metodo para atualizar particulas a cada geracao
        #         
        #a cada 40 iteraçoes pula uma geração
        # iterador == 0 a cada 40

        self.count_generations += 1
        self.best_cost_generation.append(-inf)
        self.iteration = 0
        print(f'Generation: {self.count_generations} melhor posicao:{self.best_global.position} melhor valor:{self.best_quality_global}')

    def notify_evaluation(self, value):
        """
        Notifies the algorithm that a particle position evaluation was completed.

        :param value: quality of the particle position.
        :type value: float.
        """
        # Todo: implement
        # valor qure recebeu é o melhor ja recebido?
        if value > self.best_quality_global:
            self.best_quality_global = value
            # da iteracao anterio
            # faz copia do objeto (deepcopy) pois ele vai ser alterado em sequencia
            # e utilizar '=' apenas copia a referencia
            self.best_global = copy.deepcopy(self.particles[ self.iteration ]) 
            print(f'--------melhor global: {self.best_quality_global} position:{self.best_global.position}')


        self.particles[self.iteration] = self.update_particle( self.particles[self.iteration], value)

        # conta iteracao
        self.iteration += 1
        # verifica se já iterou sobre toda a geração
        if self.iteration > self.hyperparams.num_particles - 1 :
            self.advance_generation() # verifica geracao 

    def update_particle(self, particle, value ):
        """
            Updates position and velocity for particular particle
            verifies value best of iteration and best cost

        """
      # custo da nova posicao > custo melhor ja achado para ela?
        # if J(particle.x) > J(particle.best): particle.best = particle.x
        if value > particle.best_cost:
            particle.best = particle.position
            particle.best_cost = value

        # custo da nova posicao > custo melhor da iteracao?
        # if J(particle.x) > J(best_iteration): best_iteration = particle.x
        if value > self.best_cost_generation[self.count_generations]:
             self.best_cost_generation[self.count_generations] = value
             #print(f'melhor da geracao {self.count_generations}')
            # Obtem parametros para calculo da velocidade

      # ---  atualiza posiçao e atualiza velocidade

        w    = self.hyperparams.inertia_weight
        phip = self.hyperparams.cognitive_parameter 
        phig = self.hyperparams.social_parameter

        # rp e rg aleatorios para esta particula
        rp = random.uniform(0,1)
        rg = random.uniform(0,1)

        # obtem posição e velocidade atual
        s = particle.position
        v = particle.velocity

        # calcula inertia weight
        inertia = w * v

        # calcula cognitive 
        # bi = particula.best
        cognitive = phip * rp * (particle.best - s )

        # calcula social
        best_global = self.best_global.position
        social = phig * rg * (best_global - s )

        # atualização da velocidade da particula 
        particle.velocity = inertia + cognitive + social 
        # atualizaçao da posicao da particual
        particle.position = s + particle.velocity

        return particle
