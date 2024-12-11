# run this file on a terminal using exec(open(".py").read())

import pandas as pd
from pylab import *

matplotlib.rcParams.update({'font.size': 16})  # default:10
markersize = 10
linewidth = 2

# calibration parameters
WE_OFFSET = 0 # 226  # sensor offset (in mv)
WE_SENSITIVITY = 1 # 0.3  # sensor sensitivity (in mv)

# read csv file
dataset = pd.read_csv("fan_nodrone_2.csv", delimiter=',')

# skip the last part of "laser off" (comment the following line to avoid skipping)
# dataset = dataset[:16850]

# add datetime column (with correct format)
dataset["DateTime"] = pd.to_datetime(dataset["Date"] + ' ' + dataset["Time"], format="%d/%m/%Y %H:%M:%S")

# add a column identifying laser on/off (boolean)
dataset['LASER'] = dataset['LASER-V'] > 1.99

# extract only main columns
dataset = dataset[['DateTime', 'LASER', 'WE-mv', 'AUX-mv', 'Temp']]

# pre-proecessing: averaging data per second and identifying missing data (by adding 'nan' values)
start_index = 0
current_datetime = dataset['DateTime'][start_index]

avg_datetime, avg_nb_vals, avg_we, avg_aux, avg_temp, avg_laser = [current_datetime], [0], [0.], [0.], [0.], [True]
# mean arrays (per second) of datetime, nb of values, we electrode, aux electrode, temperature, laser boolean

for i in range(start_index, len(dataset)):
    if (dataset['DateTime'][i] - current_datetime).total_seconds() == 0:
        # averaging we, aux and temp
        avg_we[-1] = (avg_we[-1] * avg_nb_vals[-1] + dataset['WE-mv'][i]) / (avg_nb_vals[-1] + 1)
        avg_aux[-1] = (avg_aux[-1] * avg_nb_vals[-1] + dataset['AUX-mv'][i]) / (avg_nb_vals[-1] + 1)
        avg_temp[-1] = (avg_temp[-1] * avg_nb_vals[-1] + dataset['Temp'][i]) / (avg_nb_vals[-1] + 1)

        # averaging laser values
        avg_laser[-1] *= dataset['LASER'][i]

        # updating nb of values
        avg_nb_vals[-1] += 1

    else:
        if (dataset['DateTime'][i] - current_datetime).total_seconds() > 1:
            # missing values --> add nan
            while (dataset['DateTime'][i] - current_datetime).total_seconds() > 1:
                current_datetime += datetime.timedelta(seconds=1)

                avg_datetime.append(current_datetime)
                avg_nb_vals.append(0)
                avg_we.append(nan)
                avg_aux.append(nan)
                avg_temp.append(nan)
                avg_laser.append(nan)

        # as we exit the while loop, we are  sure that (dataset['DateTime'][i] - current_datetime).total_seconds() == 1
        # so, let's init the new cells in the mean arrays for the current time instant
        avg_datetime.append(dataset['DateTime'][i])
        avg_nb_vals.append(1)
        avg_we.append(dataset['WE-mv'][i])
        avg_aux.append(dataset['AUX-mv'][i])
        avg_temp.append(dataset['Temp'][i])
        avg_laser.append(dataset['LASER'][i])

        # let's move current_datetime
        current_datetime = dataset['DateTime'][i]

# merging arrays into a dataframe
avg_dataset = pd.DataFrame(
    {'DateTime': avg_datetime.copy(), 'LASER': avg_laser.copy(), 'WE-mv': avg_we.copy(), 'AUX-mv': avg_aux.copy(),
     'Temp': avg_temp.copy(), 'nb_vals': avg_nb_vals.copy()})

# evaluation tests using a moving window
temp_moving_window = 60  # seconds (for temperature)
avg_moving_window = 15  # seconds (for alphasense)
std_moving_window = 60  # seconds (for alphasense)
filtered_moving_window = max([avg_moving_window, std_moving_window])  # for alphasense

std_threshold = 0.8  # mv (set to 0.8 by default)
signal_recovery = 600  # seconds

# calculating moving average of temp
moving_avg_temp = []
for i in range(temp_moving_window, len(avg_temp)):
    moving_avg_temp.append(mean(avg_temp[i - temp_moving_window:i]))

# calculating moving average of we
moving_avg_we = []
for i in range(avg_moving_window, len(avg_we)):
    moving_avg_we.append(mean(avg_we[i - avg_moving_window:i]))

# calculating moving standard deviation of we
moving_std_we = []
for i in range(std_moving_window, len(avg_we)):
    moving_std_we.append(std(avg_we[i - std_moving_window:i]))

moving_avg_aux = []
for i in range(avg_moving_window, len(avg_aux)):
    moving_avg_aux.append(mean(avg_aux[i - avg_moving_window:i]))

# calculating filtered moving average of we (based on standard deviation)
filtered_moving_avg_we = []

i = filtered_moving_window
while (i < len(avg_we)):
    if std(avg_we[i - std_moving_window:i]) < std_threshold:
        filtered_moving_avg_we.append(mean(avg_we[i - avg_moving_window:i]))
        i += 1
    else:
        for j in range(i, i + signal_recovery):
            if j >= len(avg_we):
                break
            filtered_moving_avg_we.append(nan)
        i = j + 1

# calculating calibrated moving average
calibrated_moving_average = (np.array(moving_avg_we) - WE_OFFSET + (
            0 * np.array(avg_laser[avg_moving_window:]).astype(int))) / WE_SENSITIVITY
calibrated_filtered_moving_average = (np.array(filtered_moving_avg_we) - WE_OFFSET + (
            0 * np.array(avg_laser[filtered_moving_window:]).astype(int))) / WE_SENSITIVITY

# calculating resilient calibrated moving average
resilient_moving_average = (np.array(moving_avg_we) - WE_OFFSET + (
            1 * np.array(avg_laser[avg_moving_window:]).astype(int))) / WE_SENSITIVITY
resilient_filtered_moving_average = (np.array(filtered_moving_avg_we) - WE_OFFSET + (
            1 * np.array(avg_laser[filtered_moving_window:]).astype(int))) / WE_SENSITIVITY

# *-*-*-*-plotting results-*-*-*-*#

# alphasense vs. temperature and laser
# """
fig, ax1 = plt.subplots()
# ax1.plot(range(len(avg_dataset['DateTime'])), avg_dataset['WE-mv'], color='b', label = 'Alphasense')
ax1.plot(range(len(avg_dataset['DateTime']))[avg_moving_window:], moving_avg_we, color='b', label='Alphasense')
ax1.set(ylabel='NO2 sensor output (Voltage in mV)')

ax2 = ax1.twinx()

ax2.plot(range(len(avg_dataset['DateTime']))[temp_moving_window:], moving_avg_temp, color='purple', label='DHT22')
ax2.set(ylabel='Temperature sensor (Deg. C)')
ax2.set_yticks(range(20, 30, 2))

laser_current = avg_dataset['LASER'][0]
for i in range(1, len(avg_dataset['DateTime'])):
    if avg_dataset['LASER'][i] != laser_current:
        if laser_current:
            axvline(x=i, ymin=0.05, ymax=0.95, color='y', ls='--', lw=2)
        else:
            axvline(x=i, ymin=0.05, ymax=0.95, color='r', ls='--', lw=2)
        laser_current = avg_dataset['LASER'][i]

axvline(x=4255, ymin=0.05, ymax=0.95, color='y', ls='--', lw=2)
# # axvline(x=3659, ymin=0.05, ymax=0.95, color='r', ls='--', lw=2)
axvline(x=5500, ymin=0.05, ymax=0.95, color='b', ls='--', lw=2)
ax1.set(xlabel='Time (seconds)')
ax1.legend(loc='upper right')
ax2.legend(loc='upper left')
ax1.grid()
fig.tight_layout()
fig.show()
# # """
#
# # alphasense we vs. aux
# # """
# fig, ax1 = plt.subplots()
# ax1.plot(range(len(avg_dataset['DateTime'])), avg_dataset['WE-mv'], color='b', label='Working Electrode')
# ax1.plot(range(len(avg_dataset['DateTime'])), avg_dataset['AUX-mv'], color='g', label='Auxiliary Electrode')
# ax1.set(ylabel='Voltage (mV)')
#
# ax2 = ax1.twinx()
#
# ax2.plot(range(len(avg_dataset['DateTime'])), avg_dataset['AUX-mv'] - avg_dataset['WE-mv'], color='k', label='WE - AUX')
# ax2.set(ylabel='Voltage difference (mV)')
# ax2.set_yticks(range(0, 26, 4))
#
# # ax2.plot(range(len(avg_dataset['DateTime'])), avg_dataset['LASER'], color='r')
# # ax2.set(ylabel='Laser ON/OFF')
#
# laser_current = avg_dataset['LASER'][0]
# for i in range(1, len(avg_dataset['DateTime'])):
#     if avg_dataset['LASER'][i] != laser_current:
#         if laser_current:
#             axvline(x=i, ymin=0.05, ymax=0.95, color='y', ls='--', lw=2)
#         else:
#             axvline(x=i, ymin=0.05, ymax=0.95, color='r', ls='--', lw=2)
#         laser_current = avg_dataset['LASER'][i]
#
# ax1.set(xlabel='Time (seconds)')
#
# ax1.legend(loc='upper right')
# ax2.legend(loc='upper left')
# ax1.grid()
# fig.tight_layout()
# fig.show()
# # """

# alphasense calibrated data
# """
# for i in range(10,11,10):
#
#     fig, ax1 = plt.subplots()
#
#     #calibrated_moving_average = [0. if ind<i else np.std(calibrated_moving_average[ind-i:ind]) for ind in range(0, len(calibrated_moving_average))]
#
#     ax1.plot(range(len(avg_datetime))[avg_moving_window:], calibrated_moving_average, color='b',
#              label='Standard calibration')
#
#     # ax2 = ax1.twinx()
#
#     #resilient_moving_average = [0. if ind<i else np.std(resilient_moving_average[ind-i:ind]) for ind in range(0, len(resilient_moving_average))]
#
#     ax1.plot(range(len(avg_datetime))[avg_moving_window:], resilient_moving_average, color='g', ls='--',
#              label='Resilient calibration')
#     axvline(x=4255, ymin=0.05, ymax=0.95, color='y', ls='--', lw=2)
#     # # axvline(x=3659, ymin=0.05, ymax=0.95, color='r', ls='--', lw=2)
#     axvline(x=5500, ymin=0.05, ymax=0.95, color='b', ls='--', lw=2)
#     ax1.set(ylabel='NO2 concentration (ppb)')
#     ax1.set(xlabel='Time (seconds)')
#     ax1.set_title('Std dev with '+ str(i))
#
#     ax1.legend(loc='upper right')
#     ax1.grid()
#     fig.tight_layout()
#     fig.show()
# """

# fig, ax1 = plt.subplots()
#
# calibrated_moving_average = [1. if ind<30 else np.std(calibrated_moving_average[ind-30:ind]) for ind in range(0, len(calibrated_moving_average))]
#
# ax1.plot(range(len(avg_datetime))[avg_moving_window:], calibrated_moving_average, color='b',
#          label='Standard calibration')
#
# # ax2 = ax1.twinx()
#
# resilient_moving_average = [1. if ind<30 else np.std(resilient_moving_average[ind-30:ind]) for ind in range(0, len(resilient_moving_average))]
#
# ax1.plot(range(len(avg_datetime))[avg_moving_window:], resilient_moving_average, color='g', ls='--',
#          label='Resilient calibration')
#
# axvline(x=1750, ymin=0.05, ymax=0.95, color='y', ls='--', lw=2)
# # # axvline(x=3659, ymin=0.05, ymax=0.95, color='r', ls='--', lw=2)
# axvline(x=3003, ymin=0.05, ymax=0.95, color='b', ls='--', lw=2)
# ax1.set(ylabel='NO2 concentration (ppb)')
# ax1.set(xlabel='Time (seconds)')
# ax1.set_title('Just sensor upright')
#
# ax1.legend(loc='upper right')
# ax1.grid()
# fig.tight_layout()
# fig.show()
# # """
