#Importing all packages
import pandas as pd
import numpy as np
from datetime import date, time, timedelta
import phonenumbers
import re
from scipy.stats import mode

def clean_data(data, yvc):
    print("Running Gym Sales Cleaner!")
    # Attempt to read the data into a DataFrame
    try:
        df = pd.read_csv(data)
        print("Dataframe is UTF")
    except UnicodeDecodeError:
        df = pd.read_csv(data, encoding='cp1252')
        print("Dataframe is non UTF!")


    def set_datetimes(df, date_cols):
        for col in date_cols:
            df[col] = pd.to_datetime(df[col])

    set_datetimes(df, ['Join'])

    #Filling NAs
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].fillna('')
        else:
            df[col] = df[col].fillna(0)

    #Setting the phone as string if it is not already, then stripping it of non-digits
    def phone_stripper(df, phone_cols):
        for col in phone_cols:
            if df[col].dtype=="float64":
                df[col] = df[col].apply(lambda x: str(int(x)) if x != 0 else '')
            df[col] = df[col].str.replace('\D', '', regex=True)
    phone_stripper(df, ['Home Phone 1', 'Cell Phone 1'])

    #Making sure amounts are in money format
    df['Amount'] = float(yvc)
    #Checking the total amount at the start. This should be the same as if you highlight the column in your sheet

    #checking new total
    total = df['Amount'].sum().round(2)

    #creating a temporary date column that does not include time to catch duplicates
    df['event_date'] = df['Join'].dt.date

    #Adding a country code to the phone numbers (US +1) and cleaning the phone numbers
    def add_country_code(phone):
        if pd.notnull(phone) and phone != "":
            if len(str(phone)) == 10:
                return '+1' + str(phone)
            elif len(str(phone)) == 11 and str(phone).startswith('1'):
                return '+' + str(phone)
        return phone
    # Define a function to check if a phone number is valid
    def is_valid_phone(phone):
        try:
            parsed_number = phonenumbers.parse(phone, None)
            return phonenumbers.is_valid_number(parsed_number)
        except phonenumbers.phonenumberutil.NumberParseException:
            return False
    def phone_cleaner(df, phone_cols):
        for col in phone_cols:
            df[col] = df[col].apply(add_country_code)
            # Apply the function to the 'phone' column
            df['is_valid'] = df[col].apply(is_valid_phone)

            #Removing invalid phone numbers that are not blanks
            df.loc[~df[col].apply(is_valid_phone), col] = ""

            #Removing the temporary column that checks if a phone number is valid
            df = df.drop('is_valid', axis=1)
        return df

    df = phone_cleaner(df, ['Home Phone 1', 'Cell Phone 1'])

    final = df[['Mbr First', 'Mbr Last', 'City', 'St', 'Zip', 'Email', 'Join', 'Cell Phone 1', 'Amount', 'event_date']]
    final.head()

    #Renaming columns to the proper FB versions
    column_rename = {'Mbr First': 'fn',
                    'Mbr Last': 'ln',
                    'City': 'ct',
                    'St': 'st',
                    'Email': 'email',
                    'Join': 'event_time',
                    'Home Phone 1': 'phone',
                    'Cell Phone 1': 'phone',
                    'Join': 'event_time',
                    'Amount': 'value',
                    'Zip': 'zip'}
    final = final.rename(columns=column_rename)

    # Set the time to 23:30:00
    final['event_time'] = pd.to_datetime(final['event_time']).apply(lambda x: pd.Timestamp.combine(x.date(), time(23, 30)))

    #Sorting by date/time
    final = final.sort_values(['event_time', 'phone']).reset_index(drop=True)

    #This function makes sure there are no duplicates by adding 2 minutes to time if the phone or email duplicate
    def time_offset(df, cols):
        for col in cols:
            # Filter out rows where the col value is not null or empty
            valid_entries = df[pd.notna(df[col]) & (df[col] != '')]

            duplicates = valid_entries.duplicated(subset=[col, 'event_time'])
            while duplicates.sum() > 0:  # Checking if there are any duplicates
                print(duplicates.sum())
                # Update only the valid entries
                df.loc[valid_entries.index[duplicates], 'event_time'] += timedelta(minutes=2)
                # Re-evaluate the duplicates after updating
                valid_entries = df[pd.notna(df[col]) & (df[col] != '')]
                duplicates = valid_entries.duplicated(subset=[col, 'event_time'])
                print(duplicates.sum())

        return df

    final = time_offset(final, ['phone','email'])

    #Removing columns that won't go into marketing milk or are not needed
    final = final.drop(['event_date'], axis=1)

    #Making sure order ID starts at 1 not 0
    final['order_id'] = range(1, len(final) + 1)

    #Rounding the value column. Sometimes there are multiple decimal places for some odd reason
    final['value'] = final['value'].round(2)

    #Making sure the total we have matches the total we found after clearing voided cards/orders
    new_total = final['value'].sum().round(2)
    if new_total != total:
        raise ValueError(f"new_total ({new_total}) does not match total ({total})!")

    #Every customer needs to have a positive value, so if it's 0, I change it to 0.01
    spent_nothing = final['value']<=0

    #Checking my previous action
    final.loc[spent_nothing, 'value'] = 0.01

    return final