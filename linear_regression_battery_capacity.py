import matplotlib.pyplot as plt 
import pandas as pd
from scipy import stats
import numpy as np

plt.style.use('leostyle3.mplstyle')

data_all: dict = {"Vikt": [24550,2730,1830,1960,1201,1907,11900,25400,4550,5085,20300,6005,2260,2950,5200,18000,900,1120,19000], "Batterikapacitet": [264,20,16,20,12.7,17.3,150,300,40,40,237,64,23.4,28,141,282,6,9,282]}

df_all = pd.DataFrame(data=data_all)
df_ex = df_all.iloc[:8]
df_wl = df_all.iloc[8:]

dump_liten_vikt = 25000
dump_stor_vikt = 39000
hjul_stor_vikt = 32150
band_stor_vikt = 49400

def all_in_same():
    all_slope, all_intercept, all_r_value, all_p_value, all_std_err = stats.linregress(df_all['Vikt'], df_all['Batterikapacitet'])
    ex_slope, ex_intercept, ex_r_value, ex_p_value, ex_std_err = stats.linregress(df_ex['Vikt'], df_ex['Batterikapacitet'])
    wl_slope, wl_intercept, wl_r_value, wl_p_value, wl_std_err = stats.linregress(df_wl['Vikt'], df_wl['Batterikapacitet'])

    all_line_x = np.linspace(0, max(df_all['Vikt'])+2000, 100)
    all_line_y = all_slope * all_line_x + all_intercept

    ex_line_x = np.linspace(0, max(df_all['Vikt'])+2000, 100)
    ex_line_y = ex_slope * ex_line_x + ex_intercept

    wl_line_x = np.linspace(0, max(df_all['Vikt'])+2000, 100)
    wl_line_y = wl_slope * wl_line_x + wl_intercept

    
    plt.plot(all_line_x, all_line_y, label=f'LR: ALL', color="#229CFF", linestyle="dashed", zorder=1)
    plt.plot(ex_line_x, ex_line_y, label=f'LR: EX', color="#FFB640", linestyle="dashed", zorder=1)
    plt.plot(wl_line_x, wl_line_y, label=f'LR: WL', color="#94BF73", linestyle="dashed", zorder=1)
    plt.scatter(df_ex["Vikt"], df_ex["Batterikapacitet"], color="#FF9D00", edgecolor="black", linewidths=0.5, label="ID: EX", zorder=2)
    plt.scatter(df_wl["Vikt"], df_wl["Batterikapacitet"], color="#739559", edgecolor="black", linewidths=0.5, label="ID: WL", zorder=2)
    plt.title(f"Battery capacity in relation to machine weight")
    plt.xlabel("Weight [kg]")
    plt.ylabel("Battery capacity [kWh]")
    plt.ylim(bottom=0, top=320)
    plt.legend(fontsize=16)
    plt.tight_layout()
    plt.savefig(f"./lin_reg/lin_reg_all_in_same.png", dpi=300)
    plt.show()
    

if __name__ == "__main__":
    all_in_same()




