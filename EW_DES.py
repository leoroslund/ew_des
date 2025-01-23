import numpy as np 
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import simpy
from dataclasses import dataclass, field
from cycler import cycler
import os
import argparse
import sys

class worksite():
    def __init__(self, env, *, epp, num_chargers: int = None, charging_power: int = 150, charging_threshold: float = 0.1,
                 num_wl: int = None, num_ex_b: int = None, num_ex_c: int = None, num_du: int = None,
                 workday: int = 9*3600, break_1: int = 2*3600, break_2: int = 5*3600, break_duration: int = 30*60,
                 wl_config: dict = {}, ex_config: dict = {}, du_config: dict = {}) -> None:
        
        self.env: simpy.Environment = env
        self.epp = epp
        self.chargers = simpy.Resource(env, capacity=num_chargers)
        self.charging_power: float = charging_power/3600
        self.charging_threshold: float = charging_threshold
        self.data: dict = {"battery_levels":[],
                           "power":{},
                           "inactive_machines":{}}

        # Workday
        self.workday: int = workday
        self.break_1: int = break_1
        self.break_2: int = break_2
        self.break_duration: int = break_duration

        # Machines
        self.wheel_loaders_battery = [Machine(env=env, id=f"WL #{i+1}", **wl_config) for i in range(num_wl)]
        self.dumpers_battery = [Machine(env=env, id=f"DU #{i+1}", **du_config) for i in range(num_du)]
        self.excavator_battery = [Machine(env=env, id=f"EX #{i+1}", **ex_config) for i in range(num_ex_b)]
        self.excavator_cable = [Machine(env=env, id=f"EX_C #{i+1}", **ex_config) for i in range(num_ex_c)]

        for machine in self.excavator_battery:
            env.process(self.operate_battery(machine))

        for machine in self.excavator_cable:
            env.process(self.operate_cable(machine))

        for machine in self.dumpers_battery:
            env.process(self.operate_battery(machine))

        for machine in self.wheel_loaders_battery:
            env.process(self.operate_battery(machine))
            
    def operate_cable(self, machine):
        break_1: int = self.break_1
        break_2: int = self.break_2
        break_time: int = self.break_duration
        operating_power: int = machine.operating_power

        while True:
            for power_ratio in self.epp:
                if self.env.now == break_1 or self.env.now == break_2:
                    yield self.env.timeout(break_time)
                else:
                    yield self.env.timeout(1)
                    self.log_power(power_ratio*operating_power)

    def operate_battery(self, machine):
        if machine.id.startswith(("WL", "DU")):
            operating_power: float = machine.operating_power
        else:
            operating_power: int = machine.operating_power
            sum_power_cycle: float = 0
            for power_ratio in self.epp:
                sum_power_cycle += power_ratio*operating_power
        
        charging_threshold: float = self.charging_threshold
        charging_time: int = self.break_duration

        break_1: int = self.break_1
        break_2: int = self.break_2
        no_charging: int = self.workday-1800

        while True:
            if machine.id.startswith(("WL", "DU")):
                self.log_battery_level(machine)
                self.log_machines()
                yield self.env.timeout(1)

                if self.env.now == break_1  or self.env.now == break_2:
                    yield self.env.process(self.charge(machine, charging_time))

                if machine.battery.level > charging_threshold*machine.battery.capacity:
                    yield machine.battery.get(operating_power)
                else:
                    if self.env.now < no_charging:
                        yield self.env.process(self.charge(machine, charging_time))
                    else:
                        if machine.battery.level > operating_power:
                            yield machine.battery.get(operating_power)
                        else:
                            self.data["inactive_machines"][self.env.now-1] += 1
            else:
                for power_ratio in self.epp:
                    self.log_battery_level(machine)
                    self.log_machines()
                    yield self.env.timeout(1)
                    if self.env.now == break_1 or self.env.now == break_2:
                        yield self.env.process(self.charge(machine, charging_time))

                    if machine.battery.level > charging_threshold*machine.battery.capacity:
                        yield machine.battery.get(max(power_ratio*operating_power/3600, 0.001))
                    else:
                        if self.env.now < no_charging:
                            yield self.env.process(self.charge(machine, charging_time))
                        else:
                            if machine.battery.level > power_ratio*machine.operating_power:
                                yield machine.battery.get(power_ratio*operating_power/3600)
                            else:
                                self.data["inactive_machines"][self.env.now-1] += 1

    def charge(self, machine: object, duration: int):
        charging_power: float = self.charging_power
        charging_power_kW: int = charging_power*3600
        
        with self.chargers.request() as request:
            while not request.triggered:
                if machine.id.startswith(("WL", "DU")):
                    self.log_battery_level(machine)
                    self.log_machines()
                    yield self.env.timeout(1)
                    if machine.battery.level > machine.operating_power:
                        yield machine.battery.get(machine.operating_power)
                    else:
                        self.data["inactive_machines"][self.env.now-1] += 1
                else:
                    for power_ratio in self.epp:
                        self.log_battery_level(machine)
                        self.log_machines()
                        yield self.env.timeout(1)
                        if machine.battery.level > power_ratio*machine.operating_power/3600:
                            yield machine.battery.get(max(power_ratio*machine.operating_power/3600, 0.001))
                        else:
                            self.data["inactive_machines"][self.env.now-1] += 1

            yield request
            for s in range(duration):
                self.log_battery_level(machine)
                self.log_machines()
                yield self.env.timeout(1)
                if machine.battery.level + charging_power < machine.battery.capacity:
                    yield machine.battery.put(charging_power)

                self.log_power(charging_power_kW)
    
    def log_battery_level(self, machine):
        self.data["battery_levels"].append((self.env.now, machine.id, machine.battery.level))
        
    def log_power(self, charging_power):
        time: int = self.env.now
        if time in self.data['power']:
            self.data['power'][time] += charging_power
        else:
            self.data['power'][time] = charging_power

    def log_machines(self):
        time: int = self.env.now
        self.data["inactive_machines"][time] = len(self.chargers.users)

@dataclass
class Machine:
    env: simpy.Environment
    id: str
    battery_capacity: int
    operating_power: float
    battery: simpy.Container = field(init=False)

    def __post_init__(self):
        self.battery = simpy.Container(self.env, init=self.battery_capacity, capacity=self.battery_capacity)

def simulation(simulation_settings, machine_settings, epp, save, show, grid):
    env = simpy.Environment()
    simulation_name: str = simulation_settings["name"].iloc[0]
    size_setting: str = simulation_settings["size_setting"].iloc[0]

    # Time settings
    workday: int = simulation_settings["workday"].iloc[0]
    break_1: int = simulation_settings["break_1"].iloc[0]
    break_2: int = simulation_settings["break_2"].iloc[0]
    break_duration: int = simulation_settings["break_duration"].iloc[0]
    start_time: int = simulation_settings["start_time"].iloc[0]

    # Chargers and config
    num_chargers: int = simulation_settings["num_chargers"].iloc[0]
    charging_power: int = simulation_settings["charging_power"].iloc[0]
    charging_threshold: float = simulation_settings["charging_threshold"].iloc[0]/100
    base_load: int = simulation_settings["base_load"].iloc[0]

    # Number of machines
    num_wheel_loaders: int = simulation_settings["num_wheel_loaders"].iloc[0]
    num_excavators_battery: int = simulation_settings["num_excavators_battery"].iloc[0]
    num_excavators_cable: int = simulation_settings["num_excavators_cable"].iloc[0]
    num_dumpers: int = simulation_settings["num_dumpers"].iloc[0]
    total_machines: int = num_wheel_loaders + num_dumpers + num_excavators_battery + num_excavators_cable

    def prepare_data(data) -> tuple[list, list, list]:
        battery_levels: tuple = data["battery_levels"]

        battery_levels_by_machine: dict[str, tuple] = {}
        for time, machine_id, level in battery_levels:
            if machine_id not in battery_levels_by_machine:
                battery_levels_by_machine[machine_id] = []
            battery_levels_by_machine[machine_id].append((time, level))

        grid_power_list: list[int] = []
        for t in time_array:
            grid_power_list.append(data['power'].get(t, 0) + base_load)

        active_machines: list[int] = []
        for t in time_array:
            if t > break_1 and t < break_1 + break_duration:
                active_machines.append(total_machines - num_excavators_cable - data["inactive_machines"][t])
            elif t > break_2 and t < break_2 + break_duration:
                active_machines.append(total_machines - num_excavators_cable - data["inactive_machines"][t])
            else:
                active_machines.append(total_machines - data["inactive_machines"][t])

        return battery_levels_by_machine, grid_power_list, active_machines

    def plot_data(battery_levels_by_machine: dict, grid_power_list: list, active_machines: list) -> None:    
        plt.style.use('leostyle2.mplstyle')

        def adjust_prop_cycler():
            current_cycler = plt.rcParams['axes.prop_cycle']
            color_cycle = current_cycler.by_key()['color']
            linestyle_cycle = current_cycler.by_key()['linestyle']
            
            skipped_color_cycle = color_cycle[2:] + color_cycle[:2]
            skipped_linestyle_cycle = linestyle_cycle[2:] + linestyle_cycle[:2]
            
            combined_cycler = cycler('color', skipped_color_cycle) + cycler('linestyle', skipped_linestyle_cycle)
            return combined_cycler

        def plot_setup(title: str, type: str, xlabel: str, ylabel: str, x_ticks: np.ndarray, formatter) -> None:
            plt.title(title)
            plt.xlabel(xlabel)
            plt.ylabel(ylabel)
            plt.xticks(x_ticks, rotation = 45)
            plt.gca().xaxis.set_major_formatter(FuncFormatter(formatter))
            plt.ylim(bottom=0)
            if type == "POW" and title[5:8] == "150" and title[0:3] == "MED":
                plt.ylim(top=1000)
            elif type == "POW" and title[5:8] == "150" and title[0:3] == "LAR":
                plt.ylim(top=1200)
            elif type == "POW" and title[5:8] == "350":
                plt.ylim(top=2200)
            plt.tight_layout()
            
            if not os.path.exists("./figs_testing/"):
                os.makedirs("./figs_testing/")
                print("Directory '{./figs_testing/}' created.")
            else:
                pass
            
            if save == True:
                plt.savefig(f"./figs_testing/{simulation_name}_{type}.png", dpi=300)
                if show == False:
                    plt.clf()
            if show == True:
                plt.show()

        # Plot battery levels
        if num_excavators_battery == 0:
            new_cycle = adjust_prop_cycler()
            plt.rc('axes', prop_cycle=new_cycle)

        for machine_id, levels in battery_levels_by_machine.items():
            times, battery_levels = zip(*levels)
            plt.plot(times, battery_levels, label=f"{machine_id}")
        plt.legend()
        plot_setup(f"{simulation_name}, SoC over time", "BAT", "Time", "SoC [kWh]", x_ticks, ticks_to_time)

        # Plot power usage
        plt.style.use('leostyle2.mplstyle')
        plt.plot(time_array, grid_power_list)
        plt.axhline(y=mean_power, c = "k", alpha = 0.5, ls = '--', lw = 3, label = "Average power")
        plt.legend(loc = "lower left")
        plot_setup(f"{simulation_name}, power over time", "POW", "Time", "Power [kW]", x_ticks, ticks_to_time)

        # Plot active machines
        plt.plot(time_array, active_machines)
        plot_setup(f"{simulation_name}, active machines over time", "ACT", "Time", "# active machines", x_ticks, ticks_to_time)

    def ticks_to_time(x: int, pos) -> str:
        hours: int = int((x+start_time) // 3600)
        minutes: int = int(((x+start_time) % 3600) // 60)
        return f'{hours:02d}:{minutes:02d}'
    
    # Machine config
    df_excavator_conf = machine_settings.loc[machine_settings["machine_id"] == "ex_"+size_setting]
    df_wheel_loader_conf = machine_settings.loc[machine_settings["machine_id"] == "wl_"+size_setting]
    df_dumper_conf = machine_settings.loc[machine_settings["machine_id"] == "du_"+size_setting]

    excavator_conf: dict = {'battery_capacity': df_excavator_conf["battery_capacity"].iloc[0], 'operating_power': df_excavator_conf["operating_power"].iloc[0]}
    wheel_loader_conf: dict = {'battery_capacity': df_wheel_loader_conf["battery_capacity"].iloc[0], 'operating_power': df_wheel_loader_conf["operating_power"].iloc[0]/3600}
    dumper_conf: dict = {'battery_capacity': df_dumper_conf["battery_capacity"].iloc[0], 'operating_power': df_dumper_conf["operating_power"].iloc[0]/3600}

    # Creating worksite
    worksite_instance: worksite = worksite(env, epp=epp, num_chargers=num_chargers, charging_power=charging_power, charging_threshold=charging_threshold,
                                           num_du=num_dumpers, num_ex_b=num_excavators_battery, num_ex_c=num_excavators_cable, num_wl=num_wheel_loaders, 
                                           workday=workday, break_1=break_1, break_2=break_2, break_duration=break_duration, 
                                           wl_config=wheel_loader_conf, ex_config=excavator_conf, du_config=dumper_conf)

    env.run(until=workday)

    time_array: np.ndarray = np.arange(0, workday, 1)
    x_ticks: np.ndarray = np.arange(0, workday+1, 3600)

    battery_levels, total_power, active_machines = prepare_data(worksite_instance.data)
    sum_machines = sum(active_machines)
    total_work_hours = total_machines*8
    total_worked_hours = sum_machines/3600
    missed_hours = total_work_hours - total_worked_hours
    mean_power = np.mean(total_power)

    with open("results.txt", "a") as f:
        print(f"{simulation_name}", file=f)
        print(f"Peak power [kW]: {max(total_power):.0f}", file=f)
        print(f"Average power [kW]: {mean_power:.0f}", file=f)
        print(f"Total energy demand [kWh]: {mean_power*9:.0f}", file=f)
        print(f"Productivity: {1-(missed_hours/total_work_hours) :.1%}\n", file=f)

    if grid == False:
        plot_data(battery_levels, total_power, active_machines)
    else:
        return battery_levels, total_power, active_machines

def setup_files(sim, mach, excav):
    simulation_settings = pd.read_csv(rf'{sim}', sep=',')
    machine_settings = pd.read_csv(rf'{mach}', sep=',')
    excavator_power_profile = pd.read_csv(rf'{excav}', sep=';')

    power_data = excavator_power_profile['y']
    epp = [] 
    for row in power_data:
        power_value = float(row.replace(',', '.'))
        epp.append(power_value)

    return simulation_settings, machine_settings, epp

def validate_file(file_path, description):
    if not os.path.isfile(file_path):
        return print(f"Error: {description} file not found: {file_path}")
    return file_path

def run_all(simulation_settings, machine_settings, epp, show=False, save=True, grid=False):
    for _, sim in simulation_settings.iterrows():
        sim_df = sim.to_frame().T
        size_setting = sim_df["size_setting"].iloc[0]
        machine_config = machine_settings.loc[machine_settings["size"] == str(size_setting)]
        simulation(sim_df, machine_config, epp, save, show, grid)
    if save == True:
        return print("Finished. You can find the plots in figs_testing and the results in results.txt.")
    return print("Finished. You can find the results in results.txt")
        
def run_single(simulation_name, simulation_settings, machine_settings, epp, save=False, show=True, grid=False):
    if simulation_name not in simulation_settings["name"].values:
        return print(f"There is no simulation with the name: {simulation_name}.")
    
    simulation_config = simulation_settings.loc[simulation_settings["name"] == simulation_name]
    size_setting = simulation_config["size_setting"].iloc[0]
    machine_config = machine_settings.loc[machine_settings["size"] == str(size_setting)]
    
    simulation(simulation_config, machine_config, epp, save, show, grid)
    if save == True:
        return print("Finished. You can find the plots in figs_testing and the results in results.txt.")
    return print("Finished. You can find the results in results.txt.")

def run_combined(simulation_settings, machine_settings, epp):
    simulation_groups = [["MED6B150", "MED3B150", "MED4C150", "MED2C150"],
                        ["LAR6B150", "LAR3B150", "LAR4C150", "LAR2C150"],
                        ["LAR6B350", "LAR3B350", "LAR4C350", "LAR2C350"]]
    simulations_per_figure = len(simulation_groups[0])

    workday = simulation_settings["workday"].iloc[0]
    start_time: int = simulation_settings["start_time"].iloc[0]
    num_excavators_battery: int = simulation_settings["num_excavators_battery"].iloc[0]

    time_array: np.ndarray = np.arange(0, workday, 1)
    x_ticks: np.ndarray = np.arange(0, workday+1, 3600)

    plt.style.use('leostyle2.mplstyle')

    def ticks_to_time(x: int, pos) -> str:
        hours: int = int((x+start_time) // 3600)
        minutes: int = int(((x+start_time) % 3600) // 60)
        return f'{hours:02d}:{minutes:02d}'
    
    def adjust_prop_cycler():
        current_cycler = plt.rcParams['axes.prop_cycle']
        color_cycle = current_cycler.by_key()['color']
        linestyle_cycle = current_cycler.by_key()['linestyle']
        
        skipped_color_cycle = color_cycle[2:] + color_cycle[:2]
        skipped_linestyle_cycle = linestyle_cycle[2:] + linestyle_cycle[:2]
        
        combined_cycler = cycler('color', skipped_color_cycle) + cycler('linestyle', skipped_linestyle_cycle)
        return combined_cycler

    stored_runs = {}
    for _, sim in simulation_settings.iterrows():
        sim_df = sim.to_frame().T
        size_setting = sim_df["size_setting"].iloc[0]
        machine_config = machine_settings.loc[machine_settings["size"] == str(size_setting)]
        bat, pow, act = simulation(sim_df, machine_config, epp, save=False, show=False, grid=True)
        stored_runs[sim_df["name"].iloc[0]] = bat, pow, act

    for group in simulation_groups:
        def plot_setting(title: str, type: str, ax, xlabel: str, ylabel: str, x_ticks: np.ndarray, formatter) -> None:
            ax.set_title(title)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            ax.set_xticks(x_ticks)
            for label in ax.get_xticklabels():
                label.set_rotation(45)
            ax.xaxis.set_major_formatter(FuncFormatter(formatter))
            ax.set_ylim(bottom=0)
            if type == "POW" and title[5:8] == "150" and title[0:3] == "MED":
                ax.set_ylim(top=1000)
            elif type == "POW" and title[5:8] == "150" and title[0:3] == "LAR":
                ax.set_ylim(top=1200)
            elif type == "POW" and title[5:8] == "350":
                ax.set_ylim(top=2200)

        fig, axes = plt.subplots(nrows=simulations_per_figure, ncols=3, figsize=(30, 40), dpi=300)
        for i in range(simulations_per_figure):
            simulation_name = group[i]
            bat, pow, act = stored_runs[simulation_name]

            # Plot battery levels
            num_excavators_battery = simulation_settings.loc[simulation_settings["name"] == str(simulation_name)]["num_excavators_battery"].iloc[0]

            if num_excavators_battery == 0:
                new_cycle = adjust_prop_cycler()
                axes[i, 0].set_prop_cycle(new_cycle)
                
            for machine_id, levels in bat.items():
                times, battery_levels = zip(*levels)
                axes[i, 0].plot(times, battery_levels, label=f"{machine_id}")
            axes[i, 0].legend()
            plot_setting(f"{simulation_name}, SoC over time", "BAT", axes[i, 0], "Time", "SoC [kWh]", x_ticks, ticks_to_time)

            # Plot power usage
            plt.style.use('leostyle2.mplstyle')
            axes[i, 1].plot(time_array, pow)
            axes[i, 1].axhline(y=np.mean(pow), c = "k", alpha = 0.5, ls = '--', lw = 3, label = "Average power")
            axes[i, 1].legend(loc = "lower left")
            plot_setting(f"{simulation_name}, power over time", "POW", axes[i, 1], "Time", "Power [kW]", x_ticks, ticks_to_time)

            # Plot active machines
            axes[i, 2].plot(time_array, act)
            plot_setting(f"{simulation_name}, active machines over time", "ACT", axes[i, 2], "Time", "# active machines", x_ticks, ticks_to_time)

        plt.tight_layout()
        plt.savefig(f"./figs_testing/{group[0][0:3]}_{group[0][-3:]}.png")


    return print("Finished. You can find the plots in figs_testing and the results in results.txt.")

def main(power_profile, machines, simulation_settings, save=False, show=True, grid=False):
    if power_profile == None or machines == None or simulation_settings == None:
        return print("All needed files are not provided.")

    if grid == True:
        print("Special flag called. Plots combined figures, make sure the source code finds the correct scenarios. Specified in the function \"run_combined\".")
        simulation_settings, machines, power_profile = setup_files(simulation_settings, machines, power_profile)
        run_combined(simulation_settings, machines, power_profile)
    else:
        print(f"Power profile file: {power_profile}")
        print(f"Machines file: {machines}")
        print(f"Simulation settings file: {simulation_settings}")
        print(f"Save plots: {save}")
        print(f"Show plots: {show}")
        simulation_settings, machines, power_profile = setup_files(simulation_settings, machines, power_profile)
        all_or_one = input("Do you want to run all simulations? Please answer y/n. ")
        if all_or_one.lower().strip() == "y":
            print("\nRunning all simulations...")
            run_all(simulation_settings, machines, power_profile, save=save, show=show)
        elif all_or_one.lower().strip() == "n":
            which_sim = input("Which simulation do you want to run? Please answer with simulation name i.e. \"LAR3B350\". ")
            try:
                print(f"\nRunning {which_sim}...")
                run_single(which_sim, simulation_settings, machines, power_profile, save=save, show=show, grid=False)
            except:
                return print("Could not run the simulation.")
        else:
            return print(f"Answer y or n was not provided correctly. You answered \"{all_or_one}\". Please try again.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="Run a simulation with specified settings.")
        
        parser.add_argument("--power", default="./epp.csv", help="Path to the power profile file (e.g., './power_profile.csv').")
        parser.add_argument("--machine", default="./machine_settings.csv", help="Path to the machines file (e.g., './machines.csv').")
        parser.add_argument("--simulation", default="./simulation_settings.csv", help="Path to the simulation settings file (e.g., './simulation_settings.csv').")
        parser.add_argument("--save", action="store_true", help="Called to save the plots")
        parser.add_argument("--noshow", action="store_false", help="Called to not show the plots")
        parser.add_argument("--grid", action="store_true", help="Special flag called to plot on grid")
        args = parser.parse_args()

        power_profile = validate_file(args.power, "Power profile")
        machines = validate_file(args.machine, "Machines")
        simulation_settings = validate_file(args.simulation, "Simulation settings")

        main(power_profile, machines, simulation_settings, save=args.save, show=args.noshow, grid=args.grid)

    else:
        print("No command-line arguments provided. Running with default configuration...")

        power_profile = "./epp.csv"
        machines = "./machine_settings.csv"
        simulation_settings = "./simulation_settings.csv"
        
        power_profile = validate_file(power_profile, "Default power profile")
        machines = validate_file(machines, "Default machine settings")
        simulation_settings = validate_file(simulation_settings, "Default simulation settings")

        save = False
        show = True
        grid = False

        main(power_profile, machines, simulation_settings, save=save, show=show, grid=grid)