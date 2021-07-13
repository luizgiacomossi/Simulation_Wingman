from behavior_tree import *
from constants import *


class LoyalWingmanBehaviorTree(BehaviorTree):
    """
    Represents a behavior tree of a roomba cleaning robot.
    """
    def __init__(self):
        super().__init__()
        # Todo: construct the tree here
        raiz = self.root = SelectorNode("root") # Raiz: Componente Selector

        #Construção Sequence Esquerdo
        sequenceLeft = SequenceNode("SequenciaEsquerda") # Instancia Nó Sequence lado esquerdo
        raiz.add_child(sequenceLeft) # add Nó a Raiz da arvore
        sequenceLeft.add_child(ChaseThreatNode())
        sequenceLeft.add_child(GoToFormationNode())  # Adiciona Nó de Ação a componente SequenceEsquerdo: Move Forward
        sequenceLeft.add_child(DefendLeaderNode()) # Adiciona Nó de Ação a componente SequenceEsquerdo: Move In Spiral
        
        # #Construção  Sequence Direito
        # sequenceRight = SequenceNode("SequenceDireita") # Instancia Nó Sequence lado Direito
        # raiz.add_child(sequenceRight) # add Nó a Raiz da arvore 
        # sequenceRight.add_child(GoBackNode()) # Adiciona Nó de Ação a componente SequenceDireito: Go Back
        # sequenceRight.add_child(RotateNode()) # Adiciona Nó de Ação a componente SequenceDireito: Rotate
        
## Metodos a implementar : enter() e execute() das classes a seguir

class ChaseThreatNode(LeafNode):
    '''
        Is threat in Danger Range?
    '''
    def __init__(self):
        super().__init__("ChaseThreatNode")
        # Todo: add initialization code
        self.time_executing : float # Variavel para contagem de tempo de execução 

    def enter(self, agent):
        # Todo: add enter logic
        # define velocidade linear para voltar
        self.time_executing = 0 # Reinicia tempo de execução 

    def execute(self, agent):
        # Todo: add execution logic
        # contagem de tempo executando estado
        self.time_executing += SAMPLE_TIME

        if agent.kamikazes:
            agent.check_distance_kamikazes()
            kamikaze = agent.kamikaze_to_attack 

            # se kamikaze esta proximo(400) e arma disponivel ele ira perseguir
            if agent.distance_closest_kamikaze < 400 and (agent.vaporizer_gun.available == True or agent.freezing_gun.available == True):
                agent.set_target(agent.closest_kamikaze)
                #return ExecutionStatus(2) # Go Back em Execucao

        
        return ExecutionStatus(0) # Go Back em Execucao

class GoToFormationNode(LeafNode):
    def __init__(self):
        super().__init__("GoToFormation")
        # Todo: add initialization code
        # Contagem do tempo de execucao Move Forward
        self.time_executing : float

    def enter(self, agent):
        # Todo: add enter logic
        self.time_executing = 0
        try:
            self.target
        except:
            self.target = agent.get_target()

    def execute(self, agent):
        # Todo: add execution logic
        self.target = agent.get_target()
        agent.arrive(self.target)

        self.time_executing +=1

        if (self.target - agent.location).length() < 10 and self.time_executing > 300:
            self.finished = True

        # Contagem de tempo de execuçao do estado
        self.time_executing += SAMPLE_TIME

        # retorno Status
        #if agent.get_bumper_state():
            #return ExecutionStatus(1) # Falha, Sensor bumper 
        
        #if self.time_executing > MOVE_FORWARD_TIME: 
            #return ExecutionStatus(0) # Sucesso, Move Forward pelo tempo definido
        
        return ExecutionStatus(0) # 2 Todavia em Execucao 

class DefendLeaderNode(LeafNode):
    def __init__(self):
        super().__init__("Defend Leader")
        # Todo: add initialization code
        # Contagem do tempo de execucao Move Forward
        self.time_cooldown_vaporizer = 0 
        self.time_cooldown_freezing = 0 

    def enter(self, agent):
        # Todo: add enter logic
        pass

    def execute(self, agent):
        # Todo: add execution logic

        self.time_cooldown_vaporizer += SAMPLE_TIME
        self.time_cooldown_freezing += SAMPLE_TIME

        # cheking if weapons are availiable 
        if self.time_cooldown_vaporizer > COOLDOWN_VAPORIZER:
            agent.vaporizer_gun.available = True
        
        if self.time_cooldown_freezing > COOLDOWN_FREEZING:
            agent.freezing_gun.available = True

        # check condition to attack
        if agent.distance_closest_kamikaze < 100 and self.time_cooldown_vaporizer > COOLDOWN_VAPORIZER:
            self.time_cooldown_vaporizer  = 0
            agent.fire_vaporizer(agent.closest_kamikaze)
            agent.vaporizer_gun.available = False

        kamikaze = agent.kamikaze_to_attack 
        if agent.distance_closest_kamikaze < 300 and self.time_cooldown_freezing > COOLDOWN_FREEZING and kamikaze.freezing == False:
            self.time_cooldown_freezing  = 0
            agent.fire_freezing(agent.closest_kamikaze)
            agent.freezing_gun.available = False


        # retorno Status
            #return ExecutionStatus(1) # Falha, Sensor bumper 
            #return ExecutionStatus(0) # Sucesso, Move Forward pelo tempo definido
            #return ExecutionStatus(2) # Em execuçao
        return ExecutionStatus(0) # 2 Todavia em Execucao 


class MoveInSpiralNode(LeafNode):
    def __init__(self):
        super().__init__("MoveInSpiral")
        # Todo: add initialization code
        self.radius : float # Variavel para Raio de rotaçao
        self.time_executing : float # Variavel para tempo de execução 
        self.angular_velocity : float # Variavel para calculo da velocidade angular

    def enter(self, agent):
        # Todo: add enter logic
        self.time_executing = 0 # Reinicia contagem de tempo do behavior
        self.radius = INITIAL_RADIUS_SPIRAL # Reinicia raio de rotaçao para Default 
        #print("MoveInSpiralNode")

    def execute(self, agent):
        # Todo: add execution logic
        # Incrementa tempo em execucao 
        self.time_executing += SAMPLE_TIME

        # -- Calculo velocidade angular
        # Calculo do raio segundo a lei r(t)= r0 + bt
        self.radius += SPIRAL_FACTOR * SAMPLE_TIME

        # w = v / R 
        self.angular_velocity = FORWARD_SPEED / self.radius
        agent.set_velocity(FORWARD_SPEED, self.angular_velocity) 

        # Verifica tempo de execucao Move in Spiral
        if self.time_executing > MOVE_IN_SPIRAL_TIME:
            return ExecutionStatus(0) # Spiral terminada com Sucesso

        # Verifica Sensor
        if agent.get_bumper_state(): 
            return ExecutionStatus(1)  # Sensor bumper ativado retorna falha -> Go Back

        return ExecutionStatus(2) # Spiral em execucao 

class GoBackNode(LeafNode):
    def __init__(self):
        super().__init__("GoBack")
        # Todo: add initialization code
        self.time_executing : float # Variavel para contagem de tempo de execução 

    def enter(self, agent):
        # Todo: add enter logic
        # define velocidade linear para voltar
        agent.set_velocity(BACKWARD_SPEED, 0) 
        self.time_executing = 0 # Reinicia tempo de execução 

    def execute(self, agent):
        # Todo: add execution logic
        # contagem de tempo executando estado
        self.time_executing += SAMPLE_TIME

        # t > t3 ->  Rotate
        if self.time_executing > GO_BACK_TIME:
            return ExecutionStatus(0) # Go Back terminado com Sucesso
        
        return ExecutionStatus(2) # Go Back em Execucao

class RotateNode(LeafNode):
    def __init__(self):
        super().__init__("Rotate")
        # Todo: add initialization code
        self.angle : float # Variavel para angulo aleatorio 
        self.time_for_rotatation : float # Variavel para contagem do tempo até rotacao completa
        self.terminou_rodar : bool #Variavel booleana para checagem do termino da rotacao
        self.time_executing : float # Variavel para armazenar tempo de execução

    def enter(self, agent):
        # Todo: add enter logic
        #print("RotateNode")
        self.angle = random.uniform(-math.pi, math.pi) # Gera angulo aleatorio entre -pi e pi

        # Calcula tempo para terminar rotação baseado no angulo aleatorio e velocidade angular default 
        self.time_for_rotatation = self.angle / ANGULAR_SPEED 

        self.terminou_rodar = False # Variavel de checagem de termino inicia como falsa 
        self.time_executing = 0 # reinicia contagem de tempo

    def execute(self, agent):
        # Todo: add execution logic

        # rotaçao aleatoria
        agent.set_velocity(0, ANGULAR_SPEED) # define velocidade angular para rotaçao aleatoria

        # Contagem de tempo de execucao 
        self.time_executing += SAMPLE_TIME 

        # verificacao  de rotaçao
        if self.time_executing > self.time_for_rotatation:
            return ExecutionStatus(0) # Rotaçao concluida com sucesso
        
        return ExecutionStatus(2) # Rotação em execucao 

