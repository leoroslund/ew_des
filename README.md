# EW_DES
The EW_DES model is an Electric Worksite Discrete Event Simulation model used to simulate power consumption and productivity, including battery state of charge (SoC), active machines and total power consumption for heavy duty machinery at an electric construction site. The linear regression script is a complementary script to the project used to perform a linear regression of machine weight vs battery capacity of smaller machines to determine the size of machines not yet existing.

**CURRENT PYTHON VERSION**: 3.13.0

## Simulation
To perform a simulation there are certain settings to take into consideration.

### How to run the main program
These are general steps and can be accomplished in different ways.

1. Have python 3.13.0 installed
2. Have pip installed (Python package installer) 
3. Download the necessary files (simulation.py, simulation_settings.csv, machine_settings.csv, epp.csv, requirements.txt)
4. Install the required packages (```pip install -r requirements.txt```)

When these steps are fulfilled you can run the program with different flags in your console. If running from a compiler, the main settings are;

```markdown
Power profile file: ./epp.csv
Machines file: ./machine_settings.csv
Simulation settings file: ./simulation_settings.csv
Save plots: False
Show plots: True
```

if you run ```python simulation.py -h``` you will get the following description;

```
usage: simulation.py [-h] [--power POWER] [--machine MACHINE] [--simulation SIMULATION] [--save] [--noshow] [--grid]

Run a simulation with specified settings.

options:
  -h, --help            show this help message and exit
  --power POWER         Path to the power profile file (e.g., './power_profile.csv').
  --machine MACHINE     Path to the machines file (e.g., './machines.csv').
  --simulation SIMULATION
                        Path to the simulation settings file (e.g., './simulation_settings.csv').
  --save                Called to save the plots
  --noshow              Called to not show the plots
  --grid                Special flag called to plot on grid
```

To specify specific settings files or file paths you can use the corresponding flags --power, --machine or --simulation. If no specific file is provided the program will use _./epp.csv_, _./machine_settings.csv_ and _./simulation_settings.csv_ as default.

The default use of the program only shows the plots at the end of the simulation, however, it is recommended to instead save the figures, to do so you call the script with the --save flag. Figures as save to _./figs_testing_ and the directory is created if it doesn't already exist. If you wish to only save and not show the plots you need to call the --noshow flag as well; ```python simulation.py --save --noshow```.

There is also a special flag to plot on a grid. For this to work properly you need to change the in the source code and specify the simulation groups in the _run_combined_ function. This was mainly done to plot the simulations in a comparable format suitable for the article.

```python
def run_combined(simulation_settings, machine_settings, epp):
    simulation_groups = [["MED6B150", "MED3B150", "MED4C150", "MED2C150"],
                        ["LAR6B150", "LAR3B150", "LAR4C150", "LAR2C150"],
                        ["LAR6B350", "LAR3B350", "LAR4C350", "LAR2C350"]]
...
```

When you run the program (unless you are using the --grid flag), you will be asked if you want to run all of the simulation or just a single one. 

```Do you want to run all simulations? Please answer y/n.```

Where you simply answer _y_ or _n_. If you choose _y_ all of the simulations will run and it will let you know when it is finished. If you choose _n_ you will be asked to provide the simulation name.

```Which simulation do you want to run? Please answer with simulation name i.e. "LAR3B350".```

The simulation name is the same as the "name" in simulation_settings.csv. 

When the simulation is complete you will also recieve the results in a file called _results.txt_ in the directory as your program. The results are show in the following format; 

```
LAR6B350
Peak power [kW]: 2118
Average power [kW]: 251
Total energy demand [kWh]: 2262
Productivity: 100.0%
```
**Note**: The results are always appending to the _results.txt_ file. Be sure to clear the file when necessary to avoid a large file and possible confusion between runs.

### simulation_settings.csv
This file contains all the simualtion settings, can be adjusted to whatever settings you want to use. To work they need to be in a csv format and has to follow these headers;
| name | workday | break_1 | break_2 | break_duration | start_time | num_chargers | charging_power | charging_threshold | base_load | num_wheel_loaders | num_excavators_battery | num_excavators_cable | num_dumpers | size_setting |
|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|----------|
| LAR6B150 | 32400 | 7200 | 18000 | 1800 | 25200 | 6 | 350 | 10 | 18 | 2 | 2 | 0 | 2 | lar |

**name**: Description/name of the simulation, also the name you call if only want to run 1 simulation. In the article the simulations are named after vehicle size (**LAR/MED**), number of chargers (**6/4/3/2**), excavators on battery or cable (**B/C**) and charging power (**150/350**).

**workday**: Lenght of the workday/simulation in seconds, in the article 32 400 s is used as a standard which represents an 8 hour workday with room for a total of 1 hour in breaks.

**break_1**: The time of the first break represented as seconds from the start, in the article 7 200 s is used as a standard, which is 2 hours after the start of the workday (09:00).

**break_2**: The time of the second break represented as seconds from the start, in the article 18 000 s is used as a standard, which is 5 hours after the start of the workday (12:00).

**break_duration**: The lenght of the breaks, also dictates the length of the charging time during work hours, in the article 1 800 s is used as a standard (30 min).

**start_time**: When in the day the simulation starts in seconds from midnight (00:00), in the article 25 200 s is used as a standard (07:00).

**num_chargers**: The number of chargers, in the article this value varies between 6, 4, 3 and 2 depending on the simulation. Representing either 6 battery machines with an available charger for every machine, 6 battery machines with an available charger for half of the machines (creating staggered breaks), 4 battery machines (excavators by cable) with an available charger for every machine or 4 battery machines (excavators by cable) with an available charger for half of the machines (creating staggered breaks).

**charging_power**: The charging power in kWh, in the article the charging power varies between 150 and 350, where 150 is what is normally used today and 350 is fitted towards bigger batteries in large machines.

**charging_threshold**: The threshold of when machines aim to charge if not on a break, given in percentage of battery capacity. In the article 10% is used as a standard.

**base_load**: The continuous load every second in kWh from the rest of the working site (lights, construction sheds etc). In the article 18 kWh is used as a standard.

**num_wheel_loaders**: The number of wheel loaders. In the article 2 wheel loaders are used as a standard.

**num_excavators_battery**: The number of excavators driven by battery. In the article 2 or 0 are used as a standard.

**num_excavators_cable**: The number of excavators driven by cable (directly connected to the grid). In the article 2 or 0 are used as a standard.

**num_dumpers**: The number of dump trucks. In the article 2 dump trucks are used as a standard.

**size_setting**: Determines the size of the machines, denoted by either lar (large machines) or med (medium machines). Make sure this corresponds with your machine config file (_machine_settings.csv_).

### machine_settings.csv
This file contains all the machine configurations, can be adjusted to whatever settings you want to use. To work they need to be in a csv format and has to follow these headers;
| machine_id | size | battery_capacity | operating_power |
|----------|----------|----------|----------|
| ex_lar | lar | 568 | 283 |

**machine_id**: The id of the machine config, the program uses the id to find which specific config to use, it will look for ex (excavator), du (dump truck) or wl (wheel loader) combined with the size setting (in our case lar/med).

**size**: Used to separate the machines into categories, i.e. splitting the data to only large machines to use in simulations with large machines.

**battery_capacity**: The battery capacity given in kWh.

**operating_power**: For excavators using a power profile (_epp.csv_) this values represents a maximum power in kW, while for wheel loaders and dump trucks this represents the average power and is thus used as a continuous load.

### epp.csv
This file contains the power profile of the excavator, which until further developed, needs to be in a csv file separated by semicolons and comma separation for decimal values to work. 
| x | y |
|----------|----------|
| 0 | 0,028884941 |

**x**: The second/step of the power profile, the simulation loops the profile continuously.

**y**: The percentage of power used (multiplied with the max power during the simulation).

## Linear regression
This one is hard-coded for the different machines used in the article. Can be manually adjusted to fit other machines.

![Picture of linear regression](https://github.com/leoroslund/des-glejs/blob/main/lin_reg/lin_reg_all_in_same.png?raw=true)

## Contribution
Feel free to report issues, use the model as an inspiration, and pull requests for further improvements.

