import pandas as pd
import numpy as np
from datetime import date, time, timedelta
import phonenumbers
import re
from scipy.stats import mode

def clean_data(data, restaurant, city, state):
    # Attempt to read the data into a DataFrame
    try:
        df = pd.read_csv(data, dtype={'Tab Name': str, 'Phone': str})
    except UnicodeDecodeError:
        df = pd.read_csv(data, dtype={'Tab Name': str, 'Phone': str}, encoding='cp1252')
    df['Paid Date'] = pd.to_datetime(df['Paid Date'])
    df['Order Date'] = pd.to_datetime(df['Order Date'])


    #Filling NAs with 0 for numeric columns so I can clean up phone numbers, and blanks for everything else
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].fillna('')
        else:
            df[col] = df[col].fillna(0)

    #Setting the phone as string if it is not already
    if df['Phone'].dtype=="float64":
        df['Phone'] = df['Phone'].apply(lambda x: str(int(x)) if x != 0 else '')

    #Removing non digit characters
    df['Phone'] = df['Phone'].str.replace('\D', '', regex=True)

    #Making sure amounts are in money format
    df['Amount'] = df['Amount'].round(2)
    #Checking the total amount at the start. This should be the same as if you highlight the column in your sheet
    total = df['Amount'].sum().round(2)

    #Creating list of acceptable statuses
    accepted = ['CAPTURED', 'AUTHORIZED', 'OPEN']
    df = df[df['Status'].isin(accepted)]

    #checking new total
    total = df['Amount'].sum().round(2)

    #Removing Uber and Doordash unique codes
    def extract_substring(row):
        name = row['Tab Name']
        lower_name = name.lower()
        if "UBER" in name:
            match = re.search(r'UBER\S+\s(.*)', name)
            row['Tab Name'] = match.group(1) if match else name
            row['Phone'] = ""  # Set Phone to "" for these rows
        elif "DD" in name or "CAV" in name:
            match = re.search(r'(DD|CAV)\s\S*\s(.*)', name)
            row['Tab Name'] = match.group(2) if match else name
            row['Phone'] = ""  # Set Phone to "" for these rows
        elif "grubhub" in lower_name:
            row['Tab Name'] = re.sub(r'grubhub', '', name, flags=re.IGNORECASE).strip()
        return row

    df = df.apply(extract_substring, axis=1)
    df['Tab Name'] = df['Tab Name'].str.replace('\d+', '', regex=True).str.strip().str.lower()

    df['Tab Name'].value_counts().head(10)

    #Setting names to delete
    not_names = ['to go', 'beer', 'guest', 'visa cardholder', 'togo', 'tg' ,'bar', 'front door togo', 'cardholder, visa', 'togo front door', 'tgo',
                'table', 'end', 'corner', 'west garnish', 'bar', 'east', 'west', 'bar &', 'ice', 'mid', 'buff tap',
                'west tap', 'east tap', 'tap mid', 'west buff', 'tap', '@bar', 'west buff tap', 'west end', 'east end',
                'bar -', 'table', 'band', 'bandband', 'to go!!!', 'vip', 'ciliac', 'celiac seat', 'dairy free seat', 'celiac', 'sax player',
                'valued customer', '#', 'cardmember, discover', 'catering', 'discover cardmember', 'chase visa cardholder', 'walk in', 'customer',
                'customer.', 'n\\a', 'customer,', 'employee', '-', 'out', 'walk-in', 'stage', 'taps', 'game', 'right end', 'gameroon',
                'right pole', 'left pole', 'bhnd', 'bhind', 'dish', 'end left', 'bhnd lft', 'gameroom', 'mid bar', 'behind',
                'car', 'truck', 'suv', 'white', 'black', 'silver', 'red', '.', 'jeep', 'blue', '?', ':)', 'no name',
                '??', 'van', 'the band', 'bday', 'wedding open tab', 'guy', 'guys', 'girl', 'lady', 'girls', 'ladies',
                'couple', 'go', 'reg', 'guy end', 'to go at table', 'not paid']
    # Replacing exact matches from not_names list
    df.loc[df['Tab Name'].isin(not_names), 'Tab Name'] = ""

    # Replacing cells containing 'uber-'
    df.loc[df['Tab Name'].str.contains('uber-', case=False, na=False), 'Tab Name'] = ""
    # Replacing cells containing 'postmates-'
    df.loc[df['Tab Name'].str.contains('postmates-', case=False, na=False), 'Tab Name'] = ""
    #taking out strings that end with a vehicle, as they are usually just 'black car', 'red truck', etc.
    df.loc[df['Tab Name'].str.contains(' suv$', case=False, na=False), 'Tab Name'] = ""
    df.loc[df['Tab Name'].str.contains(' car$', case=False, na=False), 'Tab Name'] = ""
    df.loc[df['Tab Name'].str.contains(' truck$', case=False, na=False), 'Tab Name'] = ""
    df.loc[df['Tab Name'].str.contains(' van$', case=False, na=False), 'Tab Name'] = ""
    df.loc[df['Tab Name'].str.contains(' jeep$', case=False, na=False), 'Tab Name'] = ""

    #Remove single characters, which are not useful as identifiers and create problems for grouping
    df.loc[df['Tab Name'].str.len() == 1, 'Tab Name'] = ''

    #Remove names with allergy, as it is quite common to have people use 'shelfish allergy' or 'peanut allergy' as a tab name
    df.loc[df['Tab Name'].str.contains(' allergy', case=False, na=False), 'Tab Name'] = ""

    df['Tab Name'].value_counts().head(10)

    df['Order Date'] = df[['Paid Date', 'Order Date']].apply(min, axis=1)

    #creating a temporary date column that does not include time to catch duplicates
    df['event_date'] = df['Order Date'].dt.date

    #Adding a country code to the phone numbers (US +1) and cleaning the phone numbers
    def add_country_code(phone):
        if pd.notnull(phone) and phone != "":
            if len(str(phone)) == 10:
                return '+1' + str(phone)
            elif len(str(phone)) == 11 and str(phone).startswith('1'):
                return '+' + str(phone)
        return phone

    df['Phone'] = df['Phone'].apply(add_country_code)

    # Define a function to check if a phone number is valid
    def is_valid_phone(phone):
        try:
            parsed_number = phonenumbers.parse(phone, None)
            return phonenumbers.is_valid_number(parsed_number)
        except phonenumbers.phonenumberutil.NumberParseException:
            return False

    # Apply the function to the 'phone' column
    df['is_valid'] = df['Phone'].apply(is_valid_phone)

    #These are invalide phone numbers
    df[(df['is_valid']==False) & (df['Phone']!="")]

    #Removing invalid phone numbers that are not blanks
    df.loc[~df['Phone'].apply(is_valid_phone), 'Phone'] = ""

    df[(df['is_valid']==False) & (df['Phone']!="")]

    #Removing the temporary column that checks if a phone number is valid
    df = df.drop('is_valid', axis=1)

    #Setting the columns I will aggregate when I group the dataframe
    agg = {
            'Email': lambda x: max(x, key=len),  # selects the longest string in 'email'
            'Phone': lambda x: max(x, key=len),  # selects the longest string in 'phone'
            'Order Date': 'min',
            'Amount': 'sum',
            'Tab Name': lambda x: max(x, key=len),  # selects the longest string in 'Tab Name'
        }

    #Creating a new dataframe that is grouped by date, order#, and location, if applicable
    grouping_columns = ['event_date', 'Order #']

    if 'Location' in df.columns:
        grouping_columns.append('Location')

    final = df.groupby(grouping_columns, as_index=False, dropna=False).agg(agg)
    final.head()

    # Creating a function to split the tab name into first and last
    def split_name(row):
        if pd.isna(row) or row == '':
            return pd.Series(['', ''])
        elif ',' in row:
            ln, fn = row.split(',', 1)
            return pd.Series([fn, ln])
        else:
            parts = row.split(' ', 1)
            if len(parts) == 1:
                return pd.Series([parts[0], ''])
            else:
                return pd.Series(parts)

    #Getting rid of leading punctuation, which can cause issues
    final['Tab Name'] = final['Tab Name'].str.replace(r'^[^a-zA-Z]*|[^a-zA-Z]*$', '', regex=True)

    #Removing extra spaces and then splitting the tab name
    final['Tab Name'] = final['Tab Name'].str.replace(r'\s+', ' ', regex=True)  # Replace multiple spaces with a single space
    final[['fn', 'ln']] = final['Tab Name'].apply(split_name)
    final['fn'] = final['fn'].str.strip()
    final['ln'] = final['ln'].str.strip()

    #Removing columns that won't go into marketing milk or are not needed
    cols_to_drop = ['Tab Name', 'Order #']

    if 'Location' in final.columns:
        cols_to_drop.append('Location')

    final = final.drop(cols_to_drop, axis=1)

    #Renaming columns to the proper FB versions
    columns = ['event_date', 'email', 'phone', 'event_time', 'value', 'fn', 'ln']
    final.columns = columns


    def duplicate_remover(final, cols):
        print(final.shape)
        text = ""
        i = 0
        for col in cols:
            if i == 0:
                text = f'(final[\"{col}\"] != \"\")'
            else:
                text += f' & (final[\"{col}\"] != \"\")'
            i+=1
        print(text)
        # Filter rows where email or phone aren't blank
        filtered_df = final[eval(text)]
        #Adding event_date to columns to check for duplication on
        cols.append('event_date')
        # Find duplicate rows
        duplicates = filtered_df.duplicated(subset=cols, keep=False)
        duplicate_rows = filtered_df[duplicates]
        print(duplicate_rows.shape)
    #This is now further grouping the data, but this time not including order #
    #This is meant to catch anyone who orders multiple times in the same day but opens a new tab
        if duplicate_rows.shape[0] != 0:
            # Define the aggregations
            aggregations = {
                'email': lambda x: max(x, key=len),  # selects the longest string in 'email'
                'phone': lambda x: max(x, key=len),  # selects the longest string in 'phone'
                'event_time': 'min',
                'value': 'sum',
                'fn': lambda x: max(x, key=len),  # selects the longest string in 'fn'
                'ln': lambda x: max(x, key=len)  # selects the longest string in 'ln'

            }
            keys_to_extract = [key for key in aggregations.keys() if key not in cols]
            new_aggs = {key: aggregations[key] for key in keys_to_extract if key in aggregations}
            print(keys_to_extract)
            # Perform the groupby and aggregation
            grouped_df = filtered_df.groupby(cols, as_index=False).agg(new_aggs)

            # Drop the original rows from the main DataFrame
            final.drop(filtered_df.index, inplace=True)

            # Append the new rows to the main DataFrame
            final = pd.concat([final, grouped_df], ignore_index=True).sort_values('event_time').reset_index(drop=True)
        print(final.shape)
        return final

    final = duplicate_remover(final, ['email', 'phone'])

    final = duplicate_remover(final, ['phone', 'fn'])

    final = duplicate_remover(final, ['email', 'fn'])

    final = duplicate_remover(final, ['phone'])

    final = duplicate_remover(final, ['email'])

    final = duplicate_remover(final, ['fn', 'ln'])

    final = duplicate_remover(final, ['event_time', 'fn'])

    #Sorting by date/time
    final = final.sort_values('event_time').reset_index()

    final.head()

    #Removing columns that won't go into marketing milk or are not needed
    final = final.drop(['event_date'], axis=1)

    #Renaming columns to the proper FB versions
    columns = ['order_id', 'email', 'phone', 'event_time', 'value', 'fn', 'ln']
    final.columns = columns

    #Making sure order ID starts at 1 not 0
    final['order_id'] = range(1, len(final) + 1)

    final.head()

    #Setting the city and state
    final['ct'] = city
    final['st'] = state

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

    #Exporting the file
    return final
