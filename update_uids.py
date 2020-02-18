from arcgis.gis import GIS
from arcgis.features import FeatureLayer

from os import path, remove

import requests
import json

base_url = ""
cw_token = ""

def get_response(url, params):
    response = requests.get(url, params=params)
    return json.loads(response.text)

def format_data(data_dict):
    token = cw_token
    json_data = json.dumps(data_dict, separators=(",",":"))
    if len(list(token)) == 0:
        params = {"data":json_data}
    else:    
        params = {"token": token, "data": json_data}
    
    return params

def get_cw_token(user, pwd):
    #Retrieve a token for Cityworks access
    data = {"LoginName": user, "Password": pwd}
    params = format_data(data)
    url = "{}/Services/authentication/authenticate".format(base_url)

    response = get_response(url, params)

    if response['Status'] is not 0:
        return "error: {}: {}".format(response['Status'],
                                      response['Message'])
    else:
        global cw_token
        cw_token = response['Value']['Token']
        return "success"
    
def get_wkid():
    #Retrieve the WKID of the cityworks layers
    data = {}
    params = format_data(data)
    url = "{}/Services/AMS/Preferences/User".format(base_url)

    response = get_response(url, params)

    try:
        return response['Value']['SpatialReference']

    except KeyError:
        return "error"
    
def get_uid_field(entity_type):
    #Retrieve the EntityUid field name for the given entity type
    data = {}
    data['EntityType'] = entity_type
    params = format_data(data)
    url = "{}/Services/AMS/Entity/EntityUidField".format(base_url)
    
    response = get_response(url, params)
    
    try:
        return response['Value']
    
    except KeyError:
        return "error"
    
def query(config, lyr, field_dict):
    oid_fld = lyr.properties.objectIdField
    rows = lyr.query(where="{} IS NULL".format(field_dict['name']))
    for row in rows.features:    
        attrs = row.attributes
        # "AAIRFIELDMARKINGLINE1"
        pot_entityuid = "{}{}".format(config['EntityType'],attrs[oid_fld])
        validate_rows = lyr.query(where="{} = '{}'".format(field_dict['name'], pot_entityuid))
        if len(validate_rows) > 0:
            msg = "Candidate UID already exists for {}:{}".format(oid_fld, attrs[oid_fld])
        else:
            set_bool = row.attributes[field_dict['name']] = pot_entityuid
            msg = lyr.edit_features(updates=[row])
        id_log = path.join(sys.path[0], "EntityUid Updates.log")
        log = open(id_log, "a")
        log.write("{}-{}".format(config['EntityType'],str(msg)))
        log.write("\n")
        log.close()        

        
def update(config):
    lyr = FeatureLayer(url=config['FeatureLyr'])
    lyr_properties = lyr.properties
    lyr_fields = lyr_properties._mapping['fields']
    entity_type = config['EntityType']
    uid_field = get_uid_field(entity_type)
    for field_dict in lyr_fields:
        field_name_upper = field_dict['name'].upper()
        if uid_field == field_name_upper:
            entity_uid_field_dict = field_dict
    if entity_uid_field_dict == None:
        return "Configured EntityUid field is not in provided Feature Layer"
    else:
        query(config, lyr, entity_uid_field_dict)
    
def main(event, context):    
    # Cityworks settings
    global base_url
    base_url = event['CityworksURL']
    cw_user = event['CityworksUsername']
    cw_password = event['CityworksPassword']    

    # ArcGIS Online/Portal settings
    org_url = event['ArcGISURL']
    username = event['ArcGISUsername']
    password = event['ArcGISPassword']

    try:
        # Connect to org/portal
        gis = GIS(org_url, username, password)
        # authenticate CW
        cw_status = get_cw_token(cw_user, cw_password)
        if "error" in cw_status:
            raise ValueError("Error Authenticating Cityworks")
        # get wkid
        global sr
        sr = get_wkid()
        if sr == "error":
            raise ValueError("Spatial reference not defined")        
        
    except Exception as ex:
        print("error: " + str(ex))
        
    else:
        for config in event['Configurations']:
            update(config)
        
    
if __name__ == "__main__":

    import sys
    
    # configfile = sys.argv[0]  # config.json
    configfile = "config.json"
    with open(configfile) as configreader:
        config = json.load(configreader)    
    
    main(config,"context")  