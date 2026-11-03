import csv
import os
import statistics
import matplotlib.pyplot as plt
from datetime import datetime
from constants import SAVE_RESULTS

class ExperimentManager(object):
    """
    Manages telemetry, metrics recording, statistical evaluation, and CSV export
    for Loyal Wingman air defense simulations and PSO runs.
    """
    def __init__(self, filename="result.csv", save_results=SAVE_RESULTS):
        self.filename = filename
        self.save_results = save_results
        self.iterations = 0

        # Metrics history
        self.history_enemies_destroyed = []
        self.time = []
        self.counter_loyalwingman_survived = []
        self.quality = []
        self.leader_survived = []
        self.protected_area_health = []
        self.end_reasons = []
        self.params_history = []

        # Ensure CSV header exists
        if self.save_results and not os.path.exists(self.filename):
            self._init_csv()

    def _init_csv(self):
        with open(self.filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "Iteration",
                "Timestamp",
                "EnemiesDestroyed",
                "LoyalSurvived",
                "TimeElapsed",
                "LeaderSurvived",
                "ProtectedAreaLife",
                "EndCondition",
                "Quality",
                "DistanceChase",
                "DistanceFormation"
            ])

    def evaluate(self, enemies_destroyed, time_elapsed, loyal_wingman_survived):
        """
        Evaluates simulation quality (reward function used by PSO).
        Higher score rewards enemies destroyed and mission duration.
        """
        reward = (enemies_destroyed ** 2) + 10.0 * time_elapsed - loyal_wingman_survived * 1000.0
        return reward

    def record_iteration(self, enemies_destroyed, time_elapsed, loyal_wingman_survived,
                         quality, leader_alive=True, protected_area_life=100,
                         end_reason="Normal", distance_chase=0.0, distance_formation=0.0):
        """
        Records a completed simulation iteration and exports telemetry to CSV.
        """
        self.history_enemies_destroyed.append(enemies_destroyed)
        self.time.append(time_elapsed)
        self.counter_loyalwingman_survived.append(loyal_wingman_survived)
        self.quality.append(quality)
        self.leader_survived.append(leader_alive)
        self.protected_area_health.append(protected_area_life)
        self.end_reasons.append(end_reason)
        self.params_history.append((distance_chase, distance_formation))
        self.iterations += 1

        if self.save_results:
            self._append_csv(enemies_destroyed, time_elapsed, loyal_wingman_survived,
                             quality, leader_alive, protected_area_life,
                             end_reason, distance_chase, distance_formation)

    def _append_csv(self, enemies_destroyed, time_elapsed, loyal_wingman_survived,
                    quality, leader_alive, protected_area_life,
                    end_reason, distance_chase, distance_formation):
        with open(self.filename, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                self.iterations,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                enemies_destroyed,
                loyal_wingman_survived,
                f"{time_elapsed:.2f}",
                leader_alive,
                protected_area_life,
                end_reason,
                f"{quality:.2f}",
                f"{distance_chase:.2f}",
                f"{distance_formation:.2f}"
            ])

    # Backward compatibility with legacy Rate_Simulation
    def save_iteration(self, enemies_destroyed, time_elapsed, loyal_wingman_survived, quality):
        self.record_iteration(enemies_destroyed, time_elapsed, loyal_wingman_survived, quality)

    def print(self):
        if not self.history_enemies_destroyed:
            print("No iterations recorded yet.")
            return

        print('=========================================|| Experiment Summary ||========================================')
        print(f"Total Iterations: {self.iterations}")
        print(f"Média de kamikazes destruídos : {statistics.mean(self.history_enemies_destroyed):.2f} (Std: {statistics.stdev(self.history_enemies_destroyed) if len(self.history_enemies_destroyed) > 1 else 0.0:.2f})")
        print(f"Média de tempo de sobrevivência : {statistics.mean(self.time):.2f}s (Std: {statistics.stdev(self.time) if len(self.time) > 1 else 0.0:.2f})")
        print(f"Média de Loyal Wingmen sobreviventes: {statistics.mean(self.counter_loyalwingman_survived):.2f}")
        print('========================================================================================================')

    def plot_graphs(self, save_figures=False):
        if self.iterations == 0:
            print("No data to plot.")
            return

        iters = list(range(1, self.iterations + 1))

        fig, axs = plt.subplots(2, 2, figsize=(12, 8))
        fig.suptitle('Loyal Wingman Defense Experiment Metrics', fontsize=16)

        # 1. Enemies Destroyed
        axs[0, 0].plot(iters, self.history_enemies_destroyed, 'r-o', markersize=4)
        axs[0, 0].set_title('Enemies Destroyed per Iteration')
        axs[0, 0].set_xlabel('Iteration')
        axs[0, 0].set_ylabel('Enemies Count')
        axs[0, 0].grid(True)

        # 2. Survival Time
        axs[0, 1].plot(iters, self.time, 'b-s', markersize=4)
        axs[0, 1].set_title('Survival Time (seconds)')
        axs[0, 1].set_xlabel('Iteration')
        axs[0, 1].set_ylabel('Time (s)')
        axs[0, 1].grid(True)

        # 3. Quality / Fitness
        axs[1, 0].plot(iters, self.quality, 'g-^', markersize=4)
        axs[1, 0].set_title('Quality (PSO Fitness Reward)')
        axs[1, 0].set_xlabel('Iteration')
        axs[1, 0].set_ylabel('Reward')
        axs[1, 0].grid(True)

        # 4. Wingmen Survived
        axs[1, 1].plot(iters, self.counter_loyalwingman_survived, 'm-d', markersize=4)
        axs[1, 1].set_title('Loyal Wingmen Survived')
        axs[1, 1].set_xlabel('Iteration')
        axs[1, 1].set_ylabel('Count')
        axs[1, 1].grid(True)

        plt.tight_layout()
        if save_figures:
            plt.savefig('experiment_metrics.png', dpi=150)
            print("Saved experiment_metrics.png")
        plt.show()
