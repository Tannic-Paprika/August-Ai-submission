import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

# Define parameters
cycle_length = 28
period_length = 7
num_cycles = 24  # Number of cycles to generate (2 years)

# Generate synthetic menstrual cycle data
start_date = datetime(2022, 1, 1)
end_date = start_date + timedelta(days=cycle_length * num_cycles)
dates = pd.date_range(start=start_date, end=end_date, freq='D')

data = {
    'Start_Date': [],
    'End_Date': [],
    'Menstrual_Period': np.zeros(len(dates)),
    'Symptoms': ''
}

for i, date in enumerate(dates):
    cycle_day = i % cycle_length
    if cycle_day == 0:
        start_cycle_date = date
        end_cycle_date = start_cycle_date + timedelta(days=cycle_length - 1)
        data['Start_Date'].append(start_cycle_date)
        data['End_Date'].append(end_cycle_date)
    if cycle_day < period_length:
        data['Menstrual_Period'][i] = 1
        # Add fake symptoms
        symptoms = random.choice(['Cramps', 'Headache', 'Fatigue', 'Mood swings', 'Bloating'])
        data['Symptoms'] += symptoms + ', '

# Create DataFrame
df = pd.DataFrame(data)

# Print the first few rows of the synthetic data
print(df.head())
