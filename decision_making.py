from behavior_tree import *
from constants import *
from math import inf
import pygame as pg
vec2 = pg.math.Vector2


class SacrificialRammingNode(LeafNode):
    """
    Executes sacrificial kinetic interception (body-block) to protect high-value assets
    (Leader or Protected Area) ONLY when weapon ammunition is completely exhausted (Winchester state).
    """
    def __init__(self, critical_radius_leader: float = 240.0, critical_radius_base: float = 260.0):
        super().__init__("SacrificialRamming")
        self.critical_radius_leader = critical_radius_leader
        self.critical_radius_base = critical_radius_base
        self.target_threat = None

    def enter(self, agent):
        self.target_threat = None

    def execute(self, agent):
        # 1. STRICT WINCHESTER CONDITION: Must have 0 ammo in both weapons
        vap_ammo = agent.vaporizer_gun.get_ammo_available() if hasattr(agent, 'vaporizer_gun') else 0
        frz_ammo = agent.freezing_gun.get_ammo_available() if hasattr(agent, 'freezing_gun') else 0
        if vap_ammo > 0 or frz_ammo > 0:
            agent.is_sacrificing = False
            agent.sacrificial_target = None
            return ExecutionStatus.FAILURE

        # 2. Check available threats
        kamikazes = getattr(agent, 'kamikazes', [])
        if not kamikazes:
            agent.is_sacrificing = False
            agent.sacrificial_target = None
            return ExecutionStatus.FAILURE

        # 3. Locate High-Value Assets
        leader_pos = None
        if getattr(agent, 'leader', None) is not None and not getattr(agent.leader, 'destroyed', False):
            leader_pos = getattr(agent.leader, 'location', None)

        base_pos = None
        base_radius = 200.0
        if getattr(agent, 'protected_area', None) is not None:
            base_pos = getattr(agent.protected_area, 'pos', getattr(agent.protected_area, 'coordenates', None))
            base_radius = getattr(agent.protected_area, 'radius', 200.0)

        # 4. Search for active threat penetrating critical perimeter
        most_critical_threat = None
        min_breach_dist = float('inf')

        for k in kamikazes:
            if getattr(k, 'destroyed', False) or getattr(k, 'explode', False):
                continue
            k_pos = getattr(k, 'location', None)
            if k_pos is None:
                continue

            is_breaching = False
            breach_urgency = float('inf')

            # Check leader breach
            if leader_pos is not None:
                d_lead = (k_pos - leader_pos).length()
                if d_lead < self.critical_radius_leader:
                    is_breaching = True
                    breach_urgency = min(breach_urgency, d_lead)

            # Check base breach
            if base_pos is not None:
                d_base = (k_pos - base_pos).length()
                if d_base < (base_radius + self.critical_radius_base):
                    is_breaching = True
                    breach_urgency = min(breach_urgency, d_base)

            if is_breaching and breach_urgency < min_breach_dist:
                min_breach_dist = breach_urgency
                most_critical_threat = k

        # 5. If no critical asset is immediately threatened, fall back to formation escort
        if most_critical_threat is None:
            agent.is_sacrificing = False
            agent.sacrificial_target = None
            return ExecutionStatus.FAILURE

        # 6. Intercept: Kinetic Ramming Pursuit
        self.target_threat = most_critical_threat
        agent.is_sacrificing = True
        agent.sacrificial_target = most_critical_threat

        # Lead-intercept prediction
        k_vel = getattr(most_critical_threat, 'velocity', vec2(0, 0))
        dist_to_threat = (most_critical_threat.location - agent.location).length()
        t_intercept = dist_to_threat / max(agent.max_speed * 1.5, 1.0)
        aim_point = most_critical_threat.location + k_vel * min(t_intercept, 25.0)

        agent.seek(aim_point)
        return ExecutionStatus.RUNNING


class LoyalWingmanBehaviorTree(BehaviorTree):
    """
    Tactical Behavior Tree for Loyal Wingman escort UAVs in MUM-T defense.
    Coordinates threat detection, escort formation keeping, weapons engagement,
    and last-resort sacrificial kinetic interception (body-block) when out of ammunition.
    """
    def __init__(self):
        super().__init__()
        root = self.root = SelectorNode("RootSelector")

        # 1. Winchester Sacrificial Branch (Out-of-ammo emergency body-block)
        root.add_child(SacrificialRammingNode())

        # 2. Primary Standoff Engagement Sequence (Weapons & Escort)
        engagement_seq = SequenceNode("ThreatEngagementSequence")
        root.add_child(engagement_seq)
        engagement_seq.add_child(ChaseThreatNode())
        engagement_seq.add_child(GoToFormationNode())
        engagement_seq.add_child(AttackThreatNode())

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
            # 1. Cooperative Hungarian Assignment Check
            assigned = getattr(agent, 'assigned_threat', None)
            if assigned is not None and not getattr(assigned, 'explode', False):
                dist = agent.location.distance_to(assigned.location)
                if dist < agent.distance_chase and (agent.vaporizer_gun.available or agent.freezing_gun.available):
                    agent.set_target(assigned.location)
                    agent.closest_kamikaze = assigned.location
                    agent.distance_closest_kamikaze = dist
                    if agent.kamikazes and assigned in agent.kamikazes:
                        agent.index_closest = agent.kamikazes.index(assigned)
                    agent.kamikaze_to_attack = assigned
                    return ExecutionStatus(0)

            # 2. Close Escort Role: remain in defensive formation around leader
            if getattr(agent, 'tactical_role', 'INTERCEPTOR') == 'CLOSE_ESCORT':
                return ExecutionStatus(0)

            # 3. Fallback: local greedy threat detection
            agent.check_distance_kamikazes()
            kamikaze = agent.kamikaze_to_attack 

            distance_chase = agent.distance_chase 
            if agent.distance_closest_kamikaze < distance_chase and (agent.vaporizer_gun.available == True):
                agent.set_target(agent.closest_kamikaze)
         ##=============================================
        
        return ExecutionStatus(0) # Go Back em Execucao

class GoToFormationNode(LeafNode):
    """
    Directs the escort UAV to maintain its designated formation slot around the leader.
    """
    def __init__(self):
        super().__init__("GoToFormation")
        self.time_executing = 0.0
        self.target = None

    def enter(self, agent):
        self.time_executing = 0.0
        self.target = agent.get_target()

    def execute(self, agent):
        self.target = agent.get_target()
        if self.target is not None:
            agent.arrive(self.target)

        self.time_executing += SAMPLE_TIME
        return ExecutionStatus.SUCCESS 

class AttackThreatNode(LeafNode):
    """
    Manages weapon cooldown cycles and triggers discharge against designated targets.
    """
    def __init__(self):
        super().__init__("Attack Threat")
        self.time_cooldown_vaporizer = 0.0
        self.time_cooldown_freezing = 0.0

    def enter(self, agent):
        pass

    def execute(self, agent):
        self.time_cooldown_vaporizer += SAMPLE_TIME
        self.time_cooldown_freezing += SAMPLE_TIME

        if self.time_cooldown_vaporizer > COOLDOWN_VAPORIZER:
            agent.vaporizer_gun.available = True
        
        if self.time_cooldown_freezing > COOLDOWN_FREEZING:
            agent.freezing_gun.available = True

        # Check conditions to discharge weapons
        if agent.distance_closest_kamikaze < 100 and self.time_cooldown_vaporizer > COOLDOWN_VAPORIZER:
            self.time_cooldown_vaporizer = 0.0
            agent.fire_vaporizer(agent.closest_kamikaze)
            agent.vaporizer_gun.available = False

        kamikaze = agent.kamikaze_to_attack 
        if (agent.distance_closest_kamikaze < 300 and self.time_cooldown_freezing > COOLDOWN_FREEZING
                and kamikaze is not None and not getattr(kamikaze, 'freezing', False)):
            self.time_cooldown_freezing = 0.0
            agent.fire_freezing(agent.closest_kamikaze)
            agent.freezing_gun.available = False

        return ExecutionStatus.SUCCESS 

class DefendProtectedAreaNode(LeafNode):
    '''
        Is threat in Danger Range?
    '''
    def __init__(self):
        super().__init__("Defend Protected Area Behavior")
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
            # check closest kamikaze to protected area
            closest_protected_area = +inf
            memory_closest = None
            for kamikaze in agent.kamikazes:
                distance_to_area = agent.protected_area.coordenates.distance_to(kamikaze.location)
                if distance_to_area < closest_protected_area:
                    closest_protected_area =distance_to_area
                    memory_closest = kamikaze
            #============================================
            # se kamikaze esta proximo e arma disponivel ele ira perseguir
            #distance_chase = agent.dist_chase_protected_area 
            distance_chase = 300
            if agent.distance_closest_kamikaze < distance_chase and (agent.vaporizer_gun.available == True):
                agent.set_target(memory_closest.location)
                #return ExecutionStatus(2) # Go Back em Execucao

        
        return ExecutionStatus(0) # Go Back em Execucao








### =========== =========== =========== =========== =========== ===========
# these behaviors are not used
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