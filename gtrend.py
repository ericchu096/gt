import os.path
import os
import requests
import time
import pandas as pd
import numpy as np
import datetime
from pytrends.request import TrendReq
from tqdm import tqdm
import multiprocessing as mp

import json

volume = {}
address = []

def get_proxies() -> list:

    if os.path.isfile("proxy_list.txt"):
        with open('proxy_list.txt', 'r') as file:
            proxies = file.readlines()
        return proxies

    response = requests.get("https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt")
    if response.status_code == 200:
        return response.text.split('\n')
    else:
        send_error(f"requesting Proxy error {response.status_code}")

def trend_token(token, ma, proxy_list):
    df = pd.DataFrame()
    for proxy in proxy_list:
        try:
            # Increase retries and timeout settings
            pytrend = TrendReq(proxies=[f"https://{proxy}"], retries=1, backoff_factor=0.1)
            pytrend.build_payload(kw_list=token, timeframe='today 1-m')
            df = pytrend.interest_over_time().tail(ma * 2)
            if not df.empty:
                df = df[token]
                print(df)
                return df  # Return if successful
            else:
                send_error(f"df is empty: {token}")
                break  # If df is empty, no need to try other proxies

        except Exception as e:
            print(e)
            send_error(f"ERROR PASS: {token}, {e}")

    return df


def increased(vol,ma):
    l = []
    for i in vol:
        token_vol = vol[i]['volume']
        if len(token_vol) > ma:
            if list(token_vol[-1].values())[0] > list(token_vol[-ma].values())[0]:
                l.append(vol[i]['symbol'])
        else:
            l.append(vol[i]['symbol'])
    return l

def df_ma(df, n):
    try:
        for col in df.columns:
            df[col] = df[col].rolling(window=n).mean()
        df.dropna()
    except Exception as e:
        send_error(f"ERROR df_ma: {e}")
        pass
    return df

def ma_to_msg(df, threshold):

    try:
        if df.iloc[-1, 0] == np.nan:
            date = (datetime.datetime.now()-datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            date = datetime.datetime.now().strftime("%Y-%m-%d")

        df = df.tail(1).transpose()
        main_token = df.iloc[0, 0]

        # print(df[date] / main)
        df['logic'] = np.where(df[date] / (max(1, main_token)) > threshold, 1, 0)
        df['larger'] = np.where(df['logic'] == 1, df.index, '')
        # df['smaller'] = np.where(df['logic'] == -1, df.index , '')

        larger = df['larger'].unique()
        # smaller = df['smaller'].unique()
        larger = ','.join(str(x) for x in larger)
        # smaller = ','.join(str(x) for x in smaller)

        msg = f"threshold={threshold}, main={main_token}, meme/main > threshold:\n"
        msg += larger
        return msg
    except Exception as e:
        send_error(f"ERROR ma_to_msg: {e}")
        return ''
    # print(df)

def send_tg(msg):
    try:
        # url = 'https://api.telegram.org/bot7072348120:AAHhHTZ3l_wg2Cc4PruCFLlReyYuOZCSpVI/sendMessage?chat_id=-4172094165&text=' + msg
        # requests.get(url)
        print(msg)
        print("message sent")
    except Exception as e:
        send_error(f"ERROR send_tg: {e}")
        pass

def send_error(error):
    try:
        url = 'https://api.telegram.org/bot6519888997:AAGPnihV-17TI8bHhp3e0DDLkcVOPcQgwDk/sendMessage?chat_id=-4116846653&text=' + error
        requests.get(url)
        print(error)
    except Exception as e:
        send_error(f"ERROR send_error:{e}")
        pass

def gtrend_main(proxies):
    with open("ray_vol.json", "r") as f:
        volume = json.load(f)

    Tokenlist = increased(volume, ma)

    send_tg(f"length: {len(Tokenlist)} \nTesting: {Tokenlist}")

    for k in range(len(Tokenlist)):
        Tokenlist[k] = Tokenlist[k] + " token"

    df = trend_token(["solana"], ma, proxies[-1])
    
    for sec in tqdm(range(sleep)):
        time.sleep(1)

    return

    for i in range(len(Tokenlist)):
        proxy_list = proxies[i:i+3] if i < len(proxies)-1 else proxies[i%len(proxies):i%len(proxies)+3]

        print(Tokenlist[i])
        df2 = trend_token([Tokenlist[i]], ma=ma, proxy_list=proxy_list)
        
        for sec in tqdm(range(sleep)):
            time.sleep(1)
        

        if not df2.empty:
            df = pd.concat([df, df2], axis=1)

        if (i+1) % 20 == 0:
            df = df_ma(df, n=ma)
            msg = ma_to_msg(df, threshold=threshold)
            send_tg(msg)

            print(f"{i + 1} is done")
            df = trend_token(["solana"], ma, proxies[-1])
            for sec in tqdm(range(sleep*2)):
                time.sleep(1)
            

    df = df_ma(df, n=ma)
    msg = ma_to_msg(df, threshold=threshold)
    send_tg(msg)

def get_token_address():

    pairadress  = []
    addressList = []
    volumedict  = {}

    url = "https://api.raydium.io/v2/main/pairs"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        # print(data)
        for i in data:
            
            pairadress.append(i["ammId"])
            addressList.append(i["baseMint"])
            volumedict[i["baseMint"]] = i["volume24h"]

    return addressList, pairadress, volumedict
    
def dexscreen(key):
    
    url = f"https://api.dexscreener.com/latest/dex/pairs/solana/{key}"
    dex = requests.get(url)
    if dex.status_code == 200:
        get_vol(dex)
        print("DONE")
        # time.sleep(2)
        # break

def get_vol(dex):

    if dex == None:
        return
    rson = dex.json()

    if rson["pairs"] == None:
        return
    
    for pair in rson['pairs']:
        if pair['dexId'] == "raydium" and pair["quoteToken"]["symbol"] == 'SOL':
            
            if update and (pair['pairAddress'] in volume):
                volume[pair['pairAddress']]['volume'].append({datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S") : pair['volume']['h24']})
                
            else:
                volume[pair['pairAddress']] = {"name"  : pair["baseToken"]["name"],
                                                "symbol" : pair["baseToken"]["symbol"], 
                                                "volume" : [{datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S") : pair['volume']['h24']}]}
                
            address.append(pair['pairAddress'])
                      
def update():
    volume = {}
    if not os.path.isfile("ray_vol.json"):
        return volume

    with open("ray_vol.json", "r") as f:
        # Load the JSON data
        volume = json.load(f)
    return volume
    # print(volume)

def fetch_vol(volume):

    combine_pairList = []

    if Vol:
        addressList, pairadress, volumedict = get_token_address()
        if update_: volume = update()

        for i in range(0,len(pairadress),30):
            combine_pairList.append(",".join(pairadress[i:i+30]))

        print("total:",len(combine_pairList))

        if mp_mode:
            pool = mp.Pool(processes=5)
            pool.map(dexscreen, combine_pairList)
            pool.close()

        else:
            for pairs30 in combine_pairList:
                dexscreen(pairs30)

        with open("ray_vol.json", 'w') as f:
            json.dump(volume, f)


#######################################################################
if "__main__" == __name__:
    ######## set parameters #############
    # google
    ma = 3
    threshold = 1
    sleep = 10

    # volume
    Vol     = True
    update_ = True
    mp_mode = True

    #####################################
    
    while (True):
        # now = datetime.datetime.now()
        # if (now.hour == 0 and now.minute == 0):
            proxies = get_proxies()
            # fetch_vol(volume)
            gtrend_main(proxies=proxies)
            break