from enum import Enum
from constants import *
import random
import math


class ExecutionStatus(Enum):
    """
    Represents the execution status of a behavior tree node.
    """
    SUCCESS = 0
    FAILURE = 1
    RUNNING = 2

class BehaviorTree(object):
    """
    Represents a behavior tree.
    """
    def __init__(self, root=None):
        """
        Creates a behavior tree.

        :param root: the behavior tree's root node.
        :type root: TreeNode
        """
        self.root = root

    def update(self, agent):
        """
        Updates the behavior tree.

        :param agent: the agent this behavior tree is being executed on.
        """
        if self.root is not None:
            self.root.execute(agent)

class TreeNode(object):
    """
    Represents a node of a behavior tree.
    """
    def __init__(self, node_name):
        """
        Creates a node of a behavior tree.

        :param node_name: the name of the node.
        """
        self.node_name = node_name
        self.parent = None

    def enter(self, agent):
        """
        This method is executed when this node is entered.

        :param agent: the agent this node is being executed on.
        """
        raise NotImplementedError("This method is abstract and must be implemented in derived classes")

    def execute(self, agent):
        """
        Executes the behavior tree node logic.

        :param agent: the agent this node is being executed on.
        :return: node status (success, failure or running)
        :rtype: ExecutionStatus
        """
        raise NotImplementedError("This method is abstract and must be implemented in derived classes")

class LeafNode(TreeNode):
    """
    Represents a leaf node of a behavior tree.
    """
    def __init__(self, node_name):
        super().__init__(node_name)

class CompositeNode(TreeNode):
    """
    Represents a composite node of a behavior tree.
    """
    def __init__(self, node_name):
        super().__init__(node_name)
        self.children = []

    def add_child(self, child):
        """
        Adds a child to this composite node.

        :param child: child to be added to this node.
        :type child: TreeNode
        """
        child.parent = self
        self.children.append(child)

class SequenceNode(CompositeNode):
    """
    Represents a sequence node of a behavior tree.
    """
    def __init__(self, node_name):
        super().__init__(node_name)
        # We need to keep track of the last running child when resuming the tree execution
        self.running_child = None

    def enter(self, agent):
        # When this node is entered, no child should be running
        self.running_child = None

    def execute(self, agent):
        if self.running_child is None:
            # If a child was not running, then the node puts its first child to run
            self.running_child = self.children[0]
            self.running_child.enter(agent)
        loop = True
        while loop:
            # Execute the running child
            status = self.running_child.execute(agent)
            if status == ExecutionStatus.FAILURE:
                # This is a sequence node, so any failure results in the node failing
                self.running_child = None
                return ExecutionStatus.FAILURE
            elif status == ExecutionStatus.RUNNING:
                # If the child is still running, then this node is also running
                return ExecutionStatus.RUNNING
            elif status == ExecutionStatus.SUCCESS:
                # If the child returned success, then we need to run the next child or declare success
                # if this was the last child
                index = self.children.index(self.running_child)
                if index + 1 < len(self.children):
                    self.running_child = self.children[index + 1]
                    self.running_child.enter(agent)
                else:
                    self.running_child = None
                    return ExecutionStatus.SUCCESS

class SelectorNode(CompositeNode):
    """
    Represents a selector node of a behavior tree.
    """
    def __init__(self, node_name):
        super().__init__(node_name)
        # We need to keep track of the last running child when resuming the tree execution
        self.running_child = None

    def enter(self, agent):
        # When this node is entered, no child should be running
        self.running_child = None

    def execute(self, agent):
        if self.running_child is None:
            # If a child was not running, then the node puts its first child to run
            self.running_child = self.children[0]
            self.running_child.enter(agent)
        loop = True
        while loop:
            # Execute the running child
            status = self.running_child.execute(agent)
            if status == ExecutionStatus.FAILURE:
                # This is a selector node, so if the current node failed, we have to try the next one.
                # If there is no child left, then all children failed and the node must declare failure.
                index = self.children.index(self.running_child)
                if index + 1 < len(self.children):
                    self.running_child = self.children[index + 1]
                    self.running_child.enter(agent)
                else:
                    self.running_child = None
                    return ExecutionStatus.FAILURE
            elif status == ExecutionStatus.RUNNING:
                # If the child is still running, then this node is also running
                return ExecutionStatus.RUNNING
            elif status == ExecutionStatus.SUCCESS:
                # If any child returns success, then this node must also declare success
                self.running_child = None
                return ExecutionStatus.SUCCESS

class LoyalWingamanBehaviorTree(BehaviorTree):
    """
    Represents a behavior tree of a roomba cleaning robot.
    """
    def __init__(self):
        super().__init__()
        # Todo: construct the tree here
        raiz = self.root = SelectorNode("root") # Raiz: Componente Selector

        #Construção Sequence Esquerdo
        sequenceLeft = SequenceNode("SequenceEsquerda") # Instancia Nó Sequence lado esquerdo
        raiz.add_child(sequenceLeft) # add Nó a Raiz da arvore
        sequenceLeft.add_child(MoveForwardNode())  # Adiciona Nó de Ação a componente SequenceEsquerdo: Move Forward
        sequenceLeft.add_child(MoveInSpiralNode()) # Adiciona Nó de Ação a componente SequenceEsquerdo: Move In Spiral
        
        #Construção  Sequence Direito
        sequenceRight = SequenceNode("SequenceDireita") # Instancia Nó Sequence lado Direito
        raiz.add_child(sequenceRight) # add Nó a Raiz da arvore 
        sequenceRight.add_child(GoBackNode()) # Adiciona Nó de Ação a componente SequenceDireito: Go Back
        sequenceRight.add_child(RotateNode()) # Adiciona Nó de Ação a componente SequenceDireito: Rotate
        
## Metodos a implementar : enter() e execute() das classes a seguir
class MoveForwardNode(LeafNode):
    def __init__(self):
        super().__init__("MoveForward")
        # Todo: add initialization code
        # Contagem do tempo de execucao Move Forward
        self.time_executing : float

    def enter(self, agent):
        # Todo: add enter logic
        agent.set_velocity(FORWARD_SPEED, 0) # seta velocidade linear 
        self.time_executing = 0
        print("MoveForwardNode")

    def execute(self, agent):
        # Todo: add execution logic

        # Contagem de tempo de execuçao do estado
        self.time_executing += SAMPLE_TIME

        # retorno Status
        if agent.get_bumper_state():
            return ExecutionStatus(1) # Falha, Sensor bumper 
        
        if self.time_executing > MOVE_FORWARD_TIME: 
            return ExecutionStatus(0) # Sucesso, Move Forward pelo tempo definido
        
        return ExecutionStatus(2) # Todavia em Execucao 

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

class KamikazeBehaviorTree(BehaviorTree):
    """
    Represents a behavior tree of a roomba cleaning robot.
    """
    def __init__(self):
        super().__init__()
        # Todo: construct the tree here
        raiz = self.root = SelectorNode("root") # Raiz: Componente Selector

        #Construção Sequence Esquerdo
        sequenceLeft = SequenceNode("SequenceEsquerda") # Instancia Nó Sequence lado esquerdo
        raiz.add_child(sequenceLeft) # add Nó a Raiz da arvore
        sequenceLeft.add_child(MoveForwardNode())  # Adiciona Nó de Ação a componente SequenceEsquerdo: Move Forward
        sequenceLeft.add_child(MoveInSpiralNode()) # Adiciona Nó de Ação a componente SequenceEsquerdo: Move In Spiral
        
        #Construção  Sequence Direito
        sequenceRight = SequenceNode("SequenceDireita") # Instancia Nó Sequence lado Direito
        raiz.add_child(sequenceRight) # add Nó a Raiz da arvore 
        sequenceRight.add_child(GoBackNode()) # Adiciona Nó de Ação a componente SequenceDireito: Go Back
        sequenceRight.add_child(RotateNode()) # Adiciona Nó de Ação a componente SequenceDireito: Rotate
     