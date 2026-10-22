"""The alert pills on the Mobile dashboard: one entry per pill, in priority order.

Each pill is a UI template helper `binary_sensor.pill_<key>` whose state is
`tmpl`. The dashboard's alert row shows the icons of the active pills in this
order, so the first entries win when more are active than the row has places.

Every pill except those in CRITICAL can be dismissed on the Alerts page: it then
stays hidden until it turns off and on again.

`color_from` (optional) names one or more enum sensors whose highest
yellow/orange/red state overrides `color` in the row and on the Alerts page.

`content` (optional) is a template shown next to the icon in the row, e.g. a count.

`secondary`, `rule`, `data`, `hist` and the optional `summary` (a line that
always shows in the pill's section, on or off) only feed the Alerts sub-page. Thresholds live
in `tmpl`; change them here and run `sync.py`, not in the HA UI, or the next
sync puts them back.
"""
f=lambda e,d=0:f"states('{e}')|float({d})"
def since(e,sec):
    return f"(now() - states.{e}.last_changed).total_seconds() > {sec}"
PHONES=["sensor.iphone_battery_level","sensor.jans_ipad_battery_level","sensor.sm_f741b_battery_level","sensor.silvs_iphone_battery_level"]
LOWBAT=("{% set skip = "+str(PHONES)+" %}"
        "{% set low = states.sensor | selectattr('attributes.device_class','defined') | selectattr('attributes.device_class','eq','battery')"
        " | rejectattr('entity_id','in',skip) | rejectattr('state','in',['unknown','unavailable']) | selectattr('state','is_number')"
        " | map(attribute='state') | map('float') | select('lt',20) | list %}"
        "{% set crit = states.binary_sensor | selectattr('attributes.device_class','defined') | selectattr('attributes.device_class','eq','battery') | selectattr('state','eq','on') | list %}")
LOWBAT_LIST=("{% set skip = "+str(PHONES)+" %}"
        "{% set low = states.sensor | selectattr('attributes.device_class','defined') | selectattr('attributes.device_class','eq','battery')"
        " | rejectattr('entity_id','in',skip) | selectattr('state','is_number') | list %}"
        "{% for s in low if s.state|float < 20 %}{{ s.name }} {{ s.state|round(0) }} %{{ ', ' if not loop.last }}{% else %}All above 20 %{% endfor %}")
UPDATES="states.update | selectattr('state','eq','on') | list"
TOMORROW="(now() + timedelta(days=1)).date()|string"
WASTE="calendar.waste_collection_schedule_zaku_entsorgung"
WASTE_DAY="(state_attr('"+WASTE+"','start_time') or '')[:10]"
FLIGHTS="(state_attr('sensor.flightradar24_current_in_area','flights') or []) | selectattr('distance','defined') | selectattr('distance','lt',3) | sort(attribute='distance') | list"
TRAIN="sensor.altdorf_zurich"
def hhmm(e): return "(states('"+e+"')|as_datetime|as_local).strftime('%H:%M') if states('"+e+"') not in ['unknown','unavailable']"
NEXT_TRAINS=("{{ "+hhmm(TRAIN+"_departure")+" else '–' }} ({{ states('"+TRAIN+"_line') }}, platform {{ states('"+TRAIN+"_platform') }}"
             "{{ ', +' ~ states('"+TRAIN+"_delay') ~ ' min' if states('"+TRAIN+"_delay')|int(0) > 0 }})"
             " · then {{ "+hhmm(TRAIN+"_departure_1")+" else '–' }} and {{ "+hhmm(TRAIN+"_departure_2")+" else '–' }}"
             " · {{ (states('"+TRAIN+"_trip_duration')|float(0) * 60)|round(0)|int }} min to Zürich"
             "{{ ', ' ~ states('"+TRAIN+"_transfers') ~ ' change(s)' if states('"+TRAIN+"_transfers')|int(0) > 0 }}")
WORKDAY_UR="binary_sensor.workday_sensor_ch_ur"
WORKDAY_ZH="binary_sensor.workday_sensor_ch_zh"
CALENDARS=["calendar.home","calendar.jan_vanthoor_copebit_ch"]
# Calendar start_time is a local "YYYY-MM-DD HH:MM:SS" string without a zone,
# so it is compared as a string against local now() formatted the same way.
SOON=("{% set a = now().strftime('%Y-%m-%d %H:%M:%S') %}{% set b = (now() + timedelta(minutes=60)).strftime('%Y-%m-%d %H:%M:%S') %}"
      "{% set ns = namespace(ev=[]) %}{% for c in "+str(CALENDARS)+" %}{% set s = state_attr(c,'start_time') or '' %}"
      "{% if not state_attr(c,'all_day') and a < s <= b %}{% set ns.ev = ns.ev + [{'t': s, 'm': state_attr(c,'message'), 'c': state_attr(c,'friendly_name')}] %}{% endif %}{% endfor %}"
      "{% set ev = ns.ev | sort(attribute='t') %}")
OFFLINE=[("camera.g4_instant_high_resolution_channel","G4 Instant camera"),("binary_sensor.nuki_bridge_connected","Nuki bridge"),
         ("binary_sensor.athom_smart_plug_fridge_status","Fridge plug"),("binary_sensor.aqara_fridge","Fridge door sensor"),
         ("sensor.aqara_fridge_temp_temperature","Fridge thermometer"),("binary_sensor.aquara_smoke_acn03","Smoke detector"),
         ("sensor.ultimatesensor_scd41_co2","ultimatesensor"),("light.home_gym_dig_quad","Home gym WLED"),
         ("lock.nuki_schmatzknauf_lock_2","Nuki lock"),("sensor.schmatzrouter_state","Router")]
DOWN=("{% set ns = namespace(d=[]) %}{% for e, n in "+str([list(x) for x in OFFLINE])+" %}"
      "{% if states(e) in ['unavailable','unknown'] or (e.endswith(('_status','_connected')) and is_state(e,'off')) %}{% set ns.d = ns.d + [n] %}{% endif %}{% endfor %}")
CLIMATES=["climate.smart_thermostat_mts200b_main_channel","climate.meross_bedroom_mts200b_main_channel","climate.meross_guest_bedroom_mts200b_main_channel_2"]
HEATING="(expand("+str(CLIMATES)+") | selectattr('attributes.hvac_action','defined') | selectattr('attributes.hvac_action','eq','heating') | list)"
PLAYERS=["media_player.living_room","media_player.unnamed_room","media_player.unnamed_room_4","media_player.spotify_jan_van_thoor"]
PLAYING="(expand("+str(PLAYERS)+") | selectattr('state','eq','playing') | list)"
WARN_HOME="sensor.altdorf_ur_weather_warning_next_24_hours"
WARN_MOUNTAINS=["sensor.andermatt_weather_warning_next_24_hours","sensor.oberalppass_weather_warning_next_24_hours"]
LEVEL_RANK="{'none': 0, 'yellow': 1, 'orange': 2, 'red': 3}"
def warn_lines(entities):
    """One line per MeteoSwiss warning: event, level, and when it starts or ends."""
    return ("{% set ns = namespace(seen=[]) %}{% for s in "+str(entities)+" %}{% for w in state_attr(s,'warnings') or [] %}"
            "{% set id = w.event ~ w.region %}{% if id not in ns.seen %}{% set ns.seen = ns.seen + [id] %}"
            "{% set on = w.onset|as_datetime|as_local %}{% set off = w.expires|as_datetime|as_local %}"
            "{{ ' · ' if ns.seen|count > 1 }}{{ w.event }} ({{ w.level }}, {{ w.region }}) "
            "{{ ('until ' ~ off.strftime('%a %H:%M')) if on <= now() else ('from ' ~ on.strftime('%a %H:%M') ~ ' to ' ~ off.strftime('%a %H:%M')) }}"
            "{% endif %}{% endfor %}{% endfor %}")
LIGHTNING="sensor.altdorf_lightning"
COMPASS=("{% set az = states('"+LIGHTNING+"_azimuth')|float(-1) %}"
         "{{ ['N','NE','E','SE','S','SW','W','NW'][((az + 22.5) // 45)|int % 8] if az >= 0 else '' }}")
# MeteoSwiss's weather radar at home, every 5 minutes (the fork's optional
# Radar sensors). Below 0.3 mm/h it's drizzle the radar sees but that barely
# wets anything.
RADAR_RAIN="sensor.altdorf_ur_radar_rain_rate"
RADAR_HAIL="sensor.altdorf_ur_radar_hail_probability"
RADAR_HAIL_SIZE="sensor.altdorf_ur_radar_hail_size"
RAINING="("+f(RADAR_RAIN)+" >= 0.3)"
RADAR_TIME="' (' ~ (state_attr('"+RADAR_RAIN+"','time')|as_datetime|as_local).strftime('%H:%M') ~ ')' if state_attr('"+RADAR_RAIN+"','time')"
REUSS="sensor.reuss_seedorf"
REUSS_LIMIT="input_number.reuss_seedorf_dog_walk_limit"
# Helpers the pills read that sync.py creates when missing. Their value is
# yours to change on the Alerts page; sync never resets it.
NUMBERS=[dict(entity=REUSS_LIMIT, name="Reuss Seedorf dog walk limit", min=50, max=700, step=10, initial=150,
              unit_of_measurement="m³/s", icon="mdi:dog-side", mode="box")]
# Frigate's train detection on the full-resolution crop of the track. A train
# can flicker in and out of the zone, so "passing" holds on for 30 s and the
# count only sees one train.
TRAIN_ON_TRACK="binary_sensor.track_hd_train_occupancy"
TRAIN_PASSING="binary_sensor.train_passing"
TRAINS_TODAY="sensor.trains_today"
TRAINS_THIS_HOUR="sensor.trains_this_hour"
# Template helpers the pills read that aren't pills; sync.py creates and updates them.
TEMPLATES=[dict(entity=TRAIN_PASSING, kind="binary_sensor", name="Train passing",
                tmpl="{{ is_state('"+TRAIN_ON_TRACK+"','on') }}",
                extra={"additional_options": {"delay_off": {"hours": 0, "minutes": 0, "seconds": 30}}})]
# History stats helpers; sync.py creates them and keeps their period and
# state class. Both keep long-term statistics, so the Trains dashboard can
# chart the hourly and daily maximum as bars; "this hour" is only for that.
HISTORY_STATS=[dict(entity=TRAINS_TODAY, name="Trains today", source=TRAIN_PASSING, state=["on"], type="count",
                    start="{{ today_at() }}", end="{{ now() }}", state_class="measurement"),
               dict(entity=TRAINS_THIS_HOUR, name="Trains this hour", source=TRAIN_PASSING, state=["on"], type="count",
                    start="{{ now().replace(minute=0, second=0, microsecond=0) }}", end="{{ now() }}",
                    state_class="measurement")]
RAIN_24H="sensor.altdorf_rain_24_h"
# Statistics helpers the pills read; sync.py creates them when missing.
STATISTICS=[dict(entity=RAIN_24H, name="Altdorf rain 24 h", source="sensor.altdorf_10_minute_rain",
                 characteristic="sum", max_age={"hours": 24, "minutes": 0, "seconds": 0},
                 sampling_size=300, precision=1)]
SCHACHEN="sensor.schachen_burglen"
BRUNNEN="sensor.vierwaldstattersee_brunnen_level"
GLETSCH="sensor.rhone_gletsch_discharge"
WARN_ALL=[WARN_HOME]+WARN_MOUNTAINS
# MeteoSwiss puts the snowfall limit in the description of rain and snow
# warnings: "Snowfall limit: 2500 - 1200 m (sinking)". The lowest number wins.
SNOWLINE=("{% set ns = namespace(low=99999) %}{% for s in "+str(WARN_ALL)+" %}{% for w in state_attr(s,'warnings') or [] %}"
          "{% for m in (w.description or '') | regex_findall('Snowfall limit:[^\\n]*') %}"
          "{% for n in m | regex_findall('[0-9]{3,4}') %}{% if n|int < ns.low %}{% set ns.low = n|int %}{% endif %}{% endfor %}"
          "{% endfor %}{% endfor %}{% endfor %}")
# MeteoSwiss's "strong" class (pollen/m³, meant for daily means; these are hourly).
POLLEN_STRONG={"alder": 70, "ash": 100, "beech": 70, "birch": 70, "grasses": 50, "hazel": 70, "oak": 70}
POLLEN="sensor.luzern_pollen"
POLLEN_HIGH=("{% set ns = namespace(hi=[]) %}{% for k, lim in "+str(POLLEN_STRONG)+".items() %}"
             "{% set v = states('"+POLLEN+"_' ~ k)|float(0) %}{% if v >= lim %}{% set ns.hi = ns.hi + [k ~ ' ' ~ (v|round(0)|int)] %}{% endif %}{% endfor %}")
PROX="sensor.1_node_prox"
# Proxmox guests and storages, found by entity id so new ones are picked up
# without editing this file: sensor.3_ct_<name>_<id>_status, sensor.4_vm_…,
# sensor.5_storage_<name>_usage.
GUESTS="states.sensor | selectattr('entity_id','match','sensor\\\\.(3_ct|4_vm)_.+_status$') | list"
GUEST_NAME="| regex_replace('^[0-9]+\\\\. (CT|VM): ','') | regex_replace(' Status$','') | replace('-(',' (')"
DOWN_GUESTS=("{% set ns = namespace(d=[]) %}{% for g in "+GUESTS+" %}"
             "{% if g.attributes.expected_state == 'running' and g.state|lower != 'running' and g.state not in ['unknown','unavailable'] %}"
             "{% set ns.d = ns.d + [(g.name "+GUEST_NAME+") ~ ': ' ~ g.state] %}{% endif %}{% endfor %}")
STORAGES="states.sensor | selectattr('entity_id','match','sensor\\\\.5_storage_.+_usage$') | list"
FULL_STORAGES=("{% set ns = namespace(f=[]) %}{% for s in "+STORAGES+" %}{% if s.state|float(0) > 85 %}"
               "{% set ns.f = ns.f + [(s.name | regex_replace('^5\\\\. Storage: ','') | regex_replace(' Usage$','')) ~ ' ' ~ (s.state|float|round(0)|int) ~ ' %'] %}{% endif %}{% endfor %}")
GUEST_TABLE=("| Guest | Status | CPU | RAM |\n|:--|:--|--:|--:|\n{% for g in "+GUESTS+" | sort(attribute='entity_id') %}{% set b = g.entity_id[:-7] %}"
             "| {{ g.name "+GUEST_NAME+" }} | {{ g.state }} | {{ states(b ~ '_cpu_usage')|float(0)|round(1) }} % "
             "| {{ states(b ~ '_ram_used')|float(0)|round(1) }} / {{ states(b ~ '_ram_total')|float(0)|round(1) }} GB |\n{% endfor %}")
STORAGE_TABLE=("| Storage | Used | Of | |\n|:--|--:|--:|--:|\n{% for s in "+STORAGES+" | sort(attribute='entity_id') %}{% set b = s.entity_id[:-6] %}"
               "| {{ s.name | regex_replace('^5\\\\. Storage: ','') | regex_replace(' Usage$','') }} | {{ states(b ~ '_used')|float(0)|round(0)|int }} GB "
               "| {{ states(b ~ '_total')|float(0)|round(0)|int }} GB | {{ s.state|float(0)|round(0)|int }} % |\n{% endfor %}")
FOHN_DIFF="sensor.altdorf_ur_fohn_pressure_difference"
FOHN_OUTLOOK="sensor.altdorf_ur_fohn_outlook"
CLIM="sensor.altdorf"
MONTH_DAYS="state_attr('"+CLIM+"_month_vs_normal','days')|int(0) >= 15"
def month_pill(key,name,icon,color,cond,secondary,rule):
    return dict(key=key,group="Climate",name=name,icon=icon,color=color,tmpl="{{ "+MONTH_DAYS+" and "+cond+" }}",
                secondary=secondary,rule=rule+" Counted from the 15th of the month, so one odd day at the start can't trigger it.",
                data=[(CLIM+"_month_vs_normal","Temperature vs normal"),(CLIM+"_month_s_rain_vs_normal","Rain vs normal"),
                      (CLIM+"_month_s_sunshine_vs_normal","Sunshine vs normal")],hist=[])
RAIN_PCT="states('"+CLIM+"_month_s_rain_vs_normal')|float(100)"
SUN_PCT="states('"+CLIM+"_month_s_sunshine_vs_normal')|float(100)"
MONTH_T="states('"+CLIM+"_month_vs_normal')|float(0)"
MONTH_TEXT=("{{ state_attr('"+CLIM+"_month_vs_normal','days') }} days: {{ '%+.1f'|format("+MONTH_T+") }} °C, "
            "{{ "+RAIN_PCT+"|round(0)|int }} % of normal rain ({{ state_attr('"+CLIM+"_month_s_rain_vs_normal','rain') }} of {{ state_attr('"+CLIM+"_month_s_rain_vs_normal','normal_rain') }} mm), "
            "{{ "+SUN_PCT+"|round(0)|int }} % of normal sunshine")
HIGH="state_attr('"+CLIM+"_high_vs_normal','high')"
LOW="state_attr('"+CLIM+"_low_vs_normal','low')"
RECORD="sensor.altdorf_record_high_for_the_date"
# Pills you clear by acting (closing a door, checking the fridge) rather than
# by acknowledging them. These can't be dismissed on the Alerts page.
CRITICAL={"smoke_or_co","front_door_open","unlocked_nobody_home","fridge_open","fridge_not_cooling","heating_while_away"}
ALERTS=[
 # --- safety
 dict(key="smoke_or_co",group="Safety",name="Smoke or CO alarm",icon="mdi:smoke-detector-alert",color="red",
   tmpl="{{ is_state('binary_sensor.aquara_smoke_acn03','on') or is_state('binary_sensor.g4_instant_co_alarm_detected','on') }}",
   secondary="Smoke {{ states('binary_sensor.aquara_smoke_acn03') }} · CO {{ states('binary_sensor.g4_instant_co_alarm_detected') }}",
   rule="On when the Aqara smoke detector or the G4 Instant CO detector raises an alarm.",
   data=[("binary_sensor.aquara_smoke_acn03","Smoke detector"),("binary_sensor.g4_instant_co_alarm_detected","CO detector"),("sensor.aquara_smoke_acn03_battery","Smoke detector battery")],hist=[]),
 dict(key="front_door_open",group="Safety",name="Front door open",icon="mdi:door-open",color="red",
   tmpl="{{ is_state('binary_sensor.nuki_schmatzknauf_door_open_2','on') and "+since("binary_sensor.nuki_schmatzknauf_door_open_2",120)+" }}",
   secondary="Open since {{ states.binary_sensor.nuki_schmatzknauf_door_open_2.last_changed | as_local | relative_time }}",
   rule="On when the front door has been open for more than 2 minutes.",
   data=[("binary_sensor.nuki_schmatzknauf_door_open_2","Door"),("lock.nuki_schmatzknauf_lock_2","Lock")],hist=[]),
 dict(key="unlocked_nobody_home",group="Safety",name="Unlocked, nobody home",icon="mdi:lock-open-alert",color="red",
   tmpl="{{ not is_state('lock.nuki_schmatzknauf_lock_2','locked') and states('lock.nuki_schmatzknauf_lock_2') not in ['unknown','unavailable'] and states.person | selectattr('state','eq','home') | list | count == 0 }}",
   secondary="Lock is {{ states('lock.nuki_schmatzknauf_lock_2') }} and everyone is away",
   rule="On when the Nuki lock isn't locked while nobody is home.",
   data=[("lock.nuki_schmatzknauf_lock_2","Lock"),("person.jan","Jan"),("person.silvia","Silvia"),("sensor.nuki_schmatzknauf_battery_2","Lock battery")],hist=[]),
 # --- kitchen
 dict(key="heating_while_away",group="Home",name="Heating while away",icon="mdi:radiator",color="deep-orange",
   tmpl="{{ "+HEATING+" | count > 0 and states.person | selectattr('state','eq','home') | list | count == 0 }}",
   secondary="{{ "+HEATING+" | map(attribute='name') | join(', ') }} heating, nobody home",
   rule="On when a Meross thermostat is actively heating while nobody is home.",
   data=[(c,n) for c,n in zip(CLIMATES,["Living area","Bedroom","Guest bedroom"])]+[("person.jan","Jan"),("person.silvia","Silvia")],hist=[]),
 dict(key="fridge_not_cooling",group="Kitchen",name="Fridge not cooling",icon="mdi:fridge-alert",color="red",
   tmpl="{{ "+f("sensor.athom_smart_plug_fridge_power",99)+" < 1 and "+since("sensor.athom_smart_plug_fridge_power",7200)+" }}",
   secondary="0 W since {{ states.sensor.athom_smart_plug_fridge_power.last_changed | as_local | relative_time }} · inside {{ states('sensor.aqara_fridge_temp_temperature') }} °C",
   rule="On when the fridge plug has drawn no power for more than 2 hours (the compressor normally cycles every hour or so).",
   data=[("sensor.athom_smart_plug_fridge_power","Fridge power"),("sensor.aqara_fridge_temp_temperature","Inside temperature"),("binary_sensor.athom_smart_plug_fridge_status","Plug online")],
   hist=["sensor.athom_smart_plug_fridge_power"]),
 dict(key="fridge_open",group="Kitchen",name="Fridge open",icon="mdi:fridge-industrial-alert-outline",color="orange",
   tmpl="{{ is_state('binary_sensor.aqara_fridge','on') and "+since("binary_sensor.aqara_fridge",60)+" }}",
   secondary="Open since {{ states.binary_sensor.aqara_fridge.last_changed | as_local | relative_time }}",
   rule="On when the fridge door has been open for more than 60 seconds.",
   data=[("binary_sensor.aqara_fridge","Fridge door"),("sensor.aqara_fridge_temp_temperature","Inside temperature")],hist=[]),
 dict(key="fridge_too_warm",group="Kitchen",name="Fridge too warm",icon="mdi:thermometer-alert",color="orange",
   tmpl="{{ "+f("sensor.aqara_fridge_temp_temperature",0)+" > 8 and "+since("sensor.aqara_fridge_temp_temperature",900)+" }}",
   secondary="{{ states('sensor.aqara_fridge_temp_temperature') }} °C inside",
   rule="On when the fridge thermometer has read above 8 °C for 15 minutes. It usually sits around 7 °C, which is warm; 4–5 °C is ideal.",
   data=[("sensor.aqara_fridge_temp_temperature","Inside temperature"),("sensor.aqara_fridge_temp_humidity","Inside humidity"),("sensor.aqara_fridge_temp_battery","Thermometer battery")],
   hist=["sensor.aqara_fridge_temp_temperature"]),
 # --- weather now (existing helpers)
 dict(key="device_offline",group="Maintenance",name="Device offline",icon="mdi:lan-disconnect",color="red",
   tmpl=DOWN+"{{ ns.d | count > 0 }}",
   secondary=DOWN+"{{ ns.d | join(', ') }} offline",
   summary=DOWN+"{{ (ns.d | join(', ') ~ ' offline') if ns.d else 'All key devices are online.' }}",
   rule="On when one of the key devices (camera, Nuki bridge and lock, fridge plug and sensors, smoke detector, ultimatesensor, home gym WLED, router) is unavailable or reports itself disconnected.",
   data=OFFLINE[:6],hist=[]),
 dict(key="guest_down",group="Proxmox",name="Guest down",icon="mdi:server-remove",color="red",
   tmpl=DOWN_GUESTS+"{{ ns.d | count > 0 }}",
   secondary=DOWN_GUESTS+"{{ ns.d | join(', ') }}",
   summary=GUEST_TABLE,
   rule="On when a VM or container that is set to start at boot isn't running. Guests you stopped on purpose (not started at boot) don't count. New guests are picked up automatically.",
   data=[("sensor.4_vm_haos_100_status","Home Assistant VM")],hist=[]),
 dict(key="hail",group="Weather now",name="Hail",icon="mdi:weather-hail",color="red",
   tmpl="{{ "+f(RADAR_HAIL)+" >= 50 }}",
   secondary="{{ "+f(RADAR_HAIL)+"|round(0)|int }} % chance of hail at home on the radar{{ ', stones up to ' ~ "+f(RADAR_HAIL_SIZE)+"|round(0)|int ~ ' mm' if "+f(RADAR_HAIL_SIZE)+" > 0 }}",
   rule="On when MeteoSwiss's radar gives a 50 % chance of hail or more over the home's square kilometre. Hail size reads 0 below 20 mm.",
   data=[(RADAR_HAIL,"Hail probability"),(RADAR_HAIL_SIZE,"Largest hail"),(RADAR_RAIN,"Rain rate")],hist=[RADAR_HAIL]),
 dict(key="storm_on_the_summits",tmpl="{{ [states('sensor.slf_imis_sca1_spjp_wind_gust')|float(0), states('sensor.slf_imis_urs1_prsf_wind_gust')|float(0)]|max >= 100 }}",group="Weather now",name="Summit storm",icon="mdi:weather-hurricane",color="red",
   secondary="{{ ["+f('sensor.slf_imis_sca1_spjp_wind_gust')+","+f('sensor.slf_imis_urs1_prsf_wind_gust')+"]|max|round(0) }} km/h gusts measured (Gross Windgällen {{ "+f('sensor.slf_imis_sca1_spjp_wind_gust')+"|round(0) }}, Gross Schijen {{ "+f('sensor.slf_imis_urs1_prsf_wind_gust')+"|round(0) }})",
   rule="On when gusts measured at Gross Windgällen or Gross Schijen reach 100 km/h.",
   data=[("sensor.slf_imis_sca1_spjp_wind_gust","Gusts Gross Windgällen"),("sensor.slf_imis_urs1_prsf_wind_gust","Gusts Gross Schijen")],
   hist=["sensor.slf_imis_sca1_spjp_wind_gust","sensor.slf_imis_urs1_prsf_wind_gust"]),
 dict(key="lightning_nearby",group="Weather now",name="Lightning nearby",icon="mdi:weather-lightning",color="yellow",
   tmpl="{{ states('"+LIGHTNING+"_counter')|int(0) > 0 and states('"+LIGHTNING+"_distance')|float(999) <= 20 and now() - states."+LIGHTNING+"_counter.last_changed < timedelta(minutes=30) }}",
   secondary="Last strike {{ states('"+LIGHTNING+"_distance')|float(0)|round(0)|int }} km "+COMPASS+" of Altdorf, {{ ((now() - states."+LIGHTNING+"_counter.last_changed).total_seconds() // 60)|int }} min ago · {{ states('"+LIGHTNING+"_counter') }} strikes within 100 km",
   rule="On when Blitzortung has seen a strike within 20 km of Altdorf in the last 30 minutes.",
   data=[(LIGHTNING+"_distance","Last strike distance"),(LIGHTNING+"_azimuth","Direction"),(LIGHTNING+"_counter","Strikes (100 km, 2 h)")],
   hist=[LIGHTNING+"_counter"]),
 dict(key="raining_now",group="Weather now",name="Raining now",icon="mdi:weather-rainy",color="blue",
   tmpl="{{ "+RAINING+" }}",
   secondary="{{ "+f(RADAR_RAIN)+"|round(1) }} mm/h at home on the radar{{ "+RADAR_TIME+" }}",
   rule="On while MeteoSwiss's radar shows at least 0.3 mm/h of rain over the home's square kilometre. It sees rain start within a minute or two; the Altdorf station's 10-minute total comes 10 minutes later.",
   data=[(RADAR_RAIN,"Rain rate (radar)"),("sensor.altdorf_10_minute_rain","Rain 10 min (station)")],hist=[RADAR_RAIN]),
 dict(key="weather_warning",group="Weather now",name="Weather warning",icon="mdi:alert-octagram",color="amber",color_from=WARN_HOME,
   tmpl="{{ states('"+WARN_HOME+"') in ['yellow','orange','red'] }}",
   secondary=warn_lines([WARN_HOME]),
   rule="On while MeteoSwiss has, or expects within 24 hours, a warning for Altdorf's region (Flüelen-Unterschächen). The icon takes the warning's colour: yellow, orange or red.",
   data=[("sensor.altdorf_ur_weather_warning","Altdorf now"),(WARN_HOME,"Altdorf next 24 h")],hist=["sensor.altdorf_ur_weather_warning"]),
 dict(key="avalanche_danger_high",tmpl="{{ [states('sensor.slf_avalanche_danger_level_altdorf_9r5z')|int(0), states('sensor.slf_avalanche_danger_level_andermatt_9pb7')|int(0)]|max >= 3 }}",group="Mountains",name="Avalanche danger",icon="mdi:alert",color="deep-orange",
   secondary="Level {{ ["+f('sensor.slf_avalanche_danger_level_altdorf_9r5z')+","+f('sensor.slf_avalanche_danger_level_andermatt_9pb7')+"]|max|int }} · Schächental {{ states('sensor.slf_avalanche_danger_level_altdorf_9r5z') }}, Nördliche Urseren {{ states('sensor.slf_avalanche_danger_level_andermatt_9pb7') }}",
   rule="On when the SLF danger level for Altdorf or Andermatt is 3 (considerable) or higher.",
   data=[("sensor.slf_avalanche_danger_level_altdorf_9r5z","Altdorf (Schächental)"),("sensor.slf_avalanche_danger_level_andermatt_9pb7","Andermatt (Nördliche Urseren)")],
   hist=["sensor.slf_avalanche_danger_level_altdorf_9r5z","sensor.slf_avalanche_danger_level_andermatt_9pb7"]),
 dict(key="remote_access_down",group="Home",name="Remote access down",icon="mdi:cloud-off-outline",color="orange",
   tmpl="{{ is_state('binary_sensor.remote_ui','off') }}",
   secondary="Nabu Casa remote UI is offline · ha.janvt.dev won't load away from home",
   rule="On when the Nabu Casa remote UI is disconnected.",
   data=[("binary_sensor.remote_ui","Remote UI")],hist=["binary_sensor.remote_ui"]),
 dict(key="backup_overdue",group="Maintenance",name="Backup overdue",icon="mdi:backup-restore",color="orange",
   tmpl="{{ is_state('binary_sensor.backups_stale','on') or (states('sensor.backup_last_successful_automatic_backup') not in ['unknown','unavailable'] and now() - as_datetime(states('sensor.backup_last_successful_automatic_backup')) > timedelta(days=2)) }}",
   secondary="Last good backup {{ as_datetime(states('sensor.backup_last_successful_automatic_backup')) | relative_time }} ago · next {{ (states('sensor.backup_next_scheduled_automatic_backup')|as_datetime|as_local).strftime('%a %H:%M') if states('sensor.backup_next_scheduled_automatic_backup') not in ['unknown','unavailable'] }}",
   rule="On when the last successful automatic backup is more than 2 days old, or HA flags its backups as stale.",
   data=[("sensor.backup_last_successful_automatic_backup","Last successful"),("sensor.backup_last_attempted_automatic_backup","Last attempted"),
         ("sensor.backup_next_scheduled_automatic_backup","Next scheduled"),("sensor.backup_backup_manager_state","Backup manager")],hist=[]),
 dict(key="air_stuffy",group="Home",name="Air is stuffy",icon="mdi:molecule-co2",color="orange",
   tmpl="{{ "+f("sensor.ultimatesensor_scd41_co2",0)+" > 1200 or "+f("sensor.ultimatesensor_voc_index",0)+" > 250 }}",
   secondary="CO₂ {{ states('sensor.ultimatesensor_scd41_co2')|round(0) }} ppm · VOC index {{ states('sensor.ultimatesensor_voc_index')|round(0) }} · open a window",
   rule="On when CO₂ is above 1200 ppm or the VOC index above 250.",
   data=[("sensor.ultimatesensor_scd41_co2","CO₂"),("sensor.ultimatesensor_voc_index","VOC index"),("sensor.ultimatesensor_nox_index","NOx index"),("sensor.ultimatesensor_pm_2_5mm_weight_concentration","PM2.5")],
   hist=["sensor.ultimatesensor_scd41_co2"]),
 # --- forecast
 dict(key="reuss_high",group="Rivers",name="Reuss too high for the dog walk",icon="mdi:dog-side",color="blue",
   tmpl="{{ states('"+REUSS+"_discharge') not in ['unknown','unavailable'] and states('"+REUSS+"_discharge')|float(0) >= states('"+REUSS_LIMIT+"')|float(9999) }}",
   secondary="{{ states('"+REUSS+"_discharge')|float(0)|round(0)|int }} m³/s at Seedorf (your limit {{ states('"+REUSS_LIMIT+"')|int }}) · 24 h max {{ state_attr('"+REUSS+"_discharge','max_24h')|float(0)|round(0)|int }} · level {{ states('"+REUSS+"_level') }} m",
   summary="{% set q = states('"+REUSS+"_discharge') %}{{ ('Now ' ~ (q|float(0)|round(0)|int) ~ ' m³/s, your limit ' ~ states('"+REUSS_LIMIT+"')|int ~ ' m³/s. FOEN flood danger level 2 starts at 280 m³/s; the yearly mean is 43.') if q not in ['unknown','unavailable'] else 'No reading from the Seedorf station yet.' }}",
   rule="On when the Reuss at Seedorf carries at least your dog walk limit (change it below; it starts at 150 m³/s).",
   data=[(REUSS+"_discharge","Discharge"),(REUSS_LIMIT,"Your limit"),(REUSS+"_level","Water level"),(REUSS+"_temperature","Water temperature")],
   hist=[REUSS+"_discharge"]),
 dict(key="reuss_rising",group="Rivers",name="Reuss rising fast",icon="mdi:trending-up",color="blue",
   tmpl="{% set q = states('"+REUSS+"_discharge')|float(0) %}{% set m = state_attr('"+REUSS+"_discharge','mean_24h')|float(0) %}{{ m > 0 and q >= 1.5 * m and q - m >= 15 }}",
   secondary="{{ states('"+REUSS+"_discharge')|float(0)|round(0)|int }} m³/s at Seedorf, {{ ((states('"+REUSS+"_discharge')|float(0) / (state_attr('"+REUSS+"_discharge','mean_24h')|float(1))) * 100 - 100)|round(0)|int }} % above its 24 h mean · your limit {{ states('"+REUSS_LIMIT+"')|int }}",
   rule="On when the Reuss at Seedorf runs at least 1.5 times its 24-hour mean and at least 15 m³/s above it: the early sign before your dog walk limit.",
   data=[(REUSS+"_discharge","Seedorf now"),(REUSS_LIMIT,"Your limit")],hist=[REUSS+"_discharge"]),
 dict(key="schachen_spate",group="Rivers",name="Schächen in spate",icon="mdi:waves-arrow-up",color="blue",
   tmpl="{% set q = states('"+SCHACHEN+"_discharge')|float(0) %}{% set m = state_attr('"+SCHACHEN+"_discharge','mean_24h')|float(0) %}{{ q >= 20 or (m > 0 and q >= 4 * m and q >= 5) }}",
   secondary="{{ states('"+SCHACHEN+"_discharge')|float(0)|round(1) }} m³/s at Bürglen (24 h mean {{ state_attr('"+SCHACHEN+"_discharge','mean_24h')|float(0)|round(1) }}, June mean 10)",
   rule="On when the Schächen at Bürglen carries 20 m³/s or more, or four times its 24-hour mean (at least 5 m³/s). FOEN publishes no danger levels for it; it averages 4.4 m³/s, 10 in June. A jump here usually comes before the Reuss.",
   data=[(SCHACHEN+"_discharge","Discharge"),(SCHACHEN+"_level","Level")],hist=[SCHACHEN+"_discharge"]),
 dict(key="lake_high",group="Rivers",name="Lake Lucerne high",icon="mdi:waves",color="blue",
   tmpl="{{ states('"+BRUNNEN+"')|float(0) >= 434.0 }}",
   secondary="{{ states('"+BRUNNEN+"') }} m at Brunnen, {{ ((states('"+BRUNNEN+"')|float(0) - 433.57) * 100)|round(0)|int }} cm above its long-term mean",
   rule="On when Lake Lucerne at Brunnen reaches 434.0 m, about 40 cm above its long-term mean of 433.57 m. FOEN publishes no danger levels for this station, so the threshold is a judgement call.",
   data=[(BRUNNEN,"Level at Brunnen")],hist=[BRUNNEN]),
 dict(key="train_delayed",group="Travel",name="Train delayed",icon="mdi:train-variant",color="deep-orange",
   tmpl="{{ is_state('"+WORKDAY_UR+"','on') and states('"+TRAIN+"_delay')|int(0) >= 5 }}",
   secondary=NEXT_TRAINS,
   summary="Next trains to Zürich: "+NEXT_TRAINS,
   rule="On on Uri workdays when the next train from Altdorf to Zürich is running at least 5 minutes late.",
   data=[(WORKDAY_UR,"Workday in Uri"),(TRAIN+"_departure","Next departure"),(TRAIN+"_delay","Delay"),(TRAIN+"_line","Line"),(TRAIN+"_platform","Platform"),
         (TRAIN+"_departure_1","Then"),(TRAIN+"_departure_2","And then"),(TRAIN+"_trip_duration","Trip time"),(TRAIN+"_transfers","Changes")],
   hist=[TRAIN+"_delay"]),
 dict(key="event_soon",group="Calendar",name="Event soon",icon="mdi:calendar-clock",color="indigo",
   tmpl=SOON+"{{ ev | count > 0 }}",
   secondary=SOON+"{% for e in ev %}{{ e.m }} at {{ e.t[11:16] }} ({{ e.c }}){{ ' · ' if not loop.last }}{% endfor %}",
   rule="On when an event in the iCloud Home or copebit calendar starts within the next hour (all-day events excluded).",
   data=[("calendar.home","Home (iCloud)"),("calendar.jan_vanthoor_copebit_ch","copebit")],hist=[]),
 dict(key="rain_next_hour",group="Forecast",name="Rain next hour",icon="mdi:umbrella",color="blue",
   tmpl="{{ "+f("sensor.altdorf_ur_chance_of_rain_next_hour",0)+" >= 60 and "+f("sensor.altdorf_ur_precipitation_next_hour",0)+" >= 0.3 }}",
   secondary="{{ states('sensor.altdorf_ur_chance_of_rain_next_hour')|round(0) }} % chance, {{ states('sensor.altdorf_ur_precipitation_next_hour') }} mm in Altdorf",
   rule="On when Altdorf's forecast gives at least a 60 % chance of rain and 0.3 mm or more in the next hour.",
   data=[("sensor.altdorf_ur_chance_of_rain_next_hour","Chance of rain"),("sensor.altdorf_ur_precipitation_next_hour","Precipitation"),("sensor.altdorf_10_minute_rain","Rain now (Altdorf)")],hist=[]),
 dict(key="frost_tonight",group="Forecast",name="Frost tonight",icon="mdi:snowflake-thermometer",color="cyan",
   tmpl="{{ states('sensor.altdorf_ur_lowest_temperature_tonight') not in ['unknown','unavailable'] and "+f("sensor.altdorf_ur_lowest_temperature_tonight",9)+" <= 0 }}",
   secondary="Down to {{ states('sensor.altdorf_ur_lowest_temperature_tonight') }} °C in Altdorf tonight",
   rule="On when Altdorf's lowest forecast temperature between 18:00 and 08:00 is 0 °C or below.",
   data=[("sensor.altdorf_ur_lowest_temperature_tonight","Lowest tonight"),("sensor.ruuvi_outside_temperature","Outside now")],hist=[]),
 dict(key="bluebird_tomorrow",group="Forecast",name="Bluebird tomorrow",icon="mdi:weather-sunny-alert",color="indigo",
   tmpl="{{ "+f("sensor.gross_windgallen_snow_tonight",0)+" >= 20 and "+f("sensor.andermatt_sunshine_tomorrow_9_15",0)+" >= 4.5 and "+f("sensor.gross_windgallen_strongest_gust_tomorrow_9_15",99)+" < 40 }}",
   secondary="About {{ states('sensor.gross_windgallen_snow_tonight')|float(0)|round(0)|int }} cm of fresh snow tonight, {{ states('sensor.andermatt_sunshine_tomorrow_9_15') }} h of sun 9–15, gusts to {{ states('sensor.gross_windgallen_strongest_gust_tomorrow_9_15')|round(0) }} km/h",
   rule="On when at least 20 mm of snow (as water) falls tonight on Gross Windgällen, roughly 20 cm of fresh powder, Andermatt gets at least 4.5 h of sun between 09:00 and 15:00 tomorrow, and gusts on Gross Windgällen stay under 40 km/h. After midnight, 'tomorrow' means the following day.",
   data=[("sensor.gross_windgallen_snow_tonight","Snow tonight (Gross Windgällen)"),("sensor.andermatt_sunshine_tomorrow_9_15","Sun tomorrow 9–15 (Andermatt)"),
         ("sensor.gross_windgallen_strongest_gust_tomorrow_9_15","Gusts tomorrow 9–15 (Gross Windgällen)"),("sensor.oberalppass_snow_tonight","Snow tonight (Oberalppass)")],hist=[]),
 dict(key="snow_coming",group="Forecast",name="Snow coming",icon="mdi:weather-snowy-heavy",color="blue",
   tmpl="{{ ["+f("sensor.andermatt_snow_next_24_hours")+","+f("sensor.altdorf_ur_snow_next_24_hours")+"]|max >= 5 }}",
   secondary="Next 24 h: Andermatt {{ states('sensor.andermatt_snow_next_24_hours') }} mm, Altdorf {{ states('sensor.altdorf_ur_snow_next_24_hours') }} mm · 48 h: Andermatt {{ states('sensor.andermatt_snow_next_48_hours') }} mm",
   rule="On when at least 5 mm of snow (water equivalent, very roughly 5 cm) is forecast within 24 hours in Andermatt or Altdorf.",
   data=[("sensor.andermatt_snow_next_24_hours","Andermatt 24 h"),("sensor.andermatt_snow_next_48_hours","Andermatt 48 h"),
         ("sensor.altdorf_ur_snow_next_24_hours","Altdorf 24 h"),("sensor.altdorf_ur_snow_next_48_hours","Altdorf 48 h")],hist=[]),
 # --- mountains / weather now (existing)
 dict(key="mountain_warning",group="Mountains",name="Mountain warning",icon="mdi:alert-octagram-outline",color="amber",color_from=WARN_MOUNTAINS,
   tmpl="{{ "+str(WARN_MOUNTAINS)+" | map('states') | select('in',['yellow','orange','red']) | list | count > 0 }}",
   secondary=warn_lines(WARN_MOUNTAINS),
   rule="On while MeteoSwiss has, or expects within 24 hours, a warning for Andermatt (Urserntal) or Oberalppass (Nördliches Tavetsch).",
   data=[("sensor.andermatt_weather_warning","Andermatt now"),(WARN_MOUNTAINS[0],"Andermatt next 24 h"),
         ("sensor.oberalppass_weather_warning","Oberalppass now"),(WARN_MOUNTAINS[1],"Oberalppass next 24 h")],hist=[]),
 dict(key="snow_line_low",group="Mountains",name="Snow line coming down",icon="mdi:snowflake-melt",color="cyan",
   tmpl=SNOWLINE+"{{ ns.low <= 1500 }}",
   secondary=SNOWLINE+"Snow down to {{ ns.low }} m according to MeteoSwiss's warnings (Andermatt lies at 1440 m)",
   rule="On when a MeteoSwiss warning for Altdorf, Andermatt or Oberalppass puts the snowfall limit at 1500 m or lower.",
   data=[(WARN_HOME,"Altdorf warnings"),(WARN_MOUNTAINS[0],"Andermatt warnings"),(WARN_MOUNTAINS[1],"Oberalppass warnings")],hist=[]),
 dict(key="fresh_snow_measured",tmpl="{{ [states('sensor.slf_imis_gos3_zwja_new_snow_1d')|float(0), states('sensor.slf_imis_tuj2_mr82_new_snow_1d')|float(0)]|max >= 5 }}",group="Mountains",name="Fresh snow",icon="mdi:snowflake",color="blue",
   secondary="+{{ ["+f('sensor.slf_imis_gos3_zwja_new_snow_1d')+","+f('sensor.slf_imis_tuj2_mr82_new_snow_1d')+"]|max|round(0) }} cm in 24 h · Gütsch {{ "+f('sensor.slf_imis_gos3_zwja_snow_height')+"|round(0) }} cm, Culmatsch {{ "+f('sensor.slf_imis_tuj2_mr82_snow_height')+"|round(0) }} cm total",
   rule="On when Gütsch or Culmatsch measure at least 5 cm of new snow in 24 hours.",
   data=[("sensor.slf_imis_gos3_zwja_new_snow_1d","New snow Gütsch"),("sensor.slf_imis_tuj2_mr82_new_snow_1d","New snow Culmatsch"),
         ("sensor.slf_imis_gos3_zwja_snow_height","Snow depth Gütsch"),("sensor.slf_imis_tuj2_mr82_snow_height","Snow depth Culmatsch")],
   hist=["sensor.slf_imis_gos3_zwja_snow_height","sensor.slf_imis_tuj2_mr82_snow_height"]),
 dict(key="fohn_altdorf",tmpl="{% set d = states('sensor.altdorf_wind_direction')|float(-1) %}\n{% set g = states('sensor.altdorf_wind_speed_max')|float(0) %}\n{% set w = states('sensor.altdorf_wind_speed')|float(0) %}\n{% set h = states('sensor.altdorf_humidity')|float(100) %}\n{% set dt = states('sensor.altdorf_temperature')|float(0) - states('sensor.zurich_fluntern_temperature')|float(99) %}\n{% set rule = 110 <= d <= 220 and (w >= 15 or g >= 35) and h < 50 and dt >= 5 %}{% set i = states('sensor.altdorf_fohn') %}{{ i == 'foehn' or (i in ['mixed','unknown','unavailable'] and rule) }}",group="Weather now",name="Föhn in Altdorf",icon="mdi:weather-windy",color="amber",
   secondary="Wind {{ "+f('sensor.altdorf_wind_speed')+"|round(0) }} km/h, gusts {{ "+f('sensor.altdorf_wind_speed_max')+"|round(0) }} km/h from {{ "+f('sensor.altdorf_wind_direction')+"|round(0) }}°, {{ "+f('sensor.altdorf_humidity')+"|round(0) }} % humidity, {{ ("+f('sensor.altdorf_temperature')+" - "+f('sensor.zurich_fluntern_temperature')+")|round(1) }} °C warmer than Zürich",
   rule="On when MeteoSwiss's Föhn index for Altdorf says föhn. When it says 'mixed', or isn't available, Altdorf also needs wind from 110–220°, 15 km/h of wind or 35 km/h gusts, humidity under 50 %, and to be 5 °C warmer than Zürich.",
   data=[("sensor.altdorf_fohn","MeteoSwiss Föhn index"),("sensor.altdorf_wind_speed","Wind"),("sensor.altdorf_wind_speed_max","Gusts"),("sensor.altdorf_wind_direction","Direction"),("sensor.altdorf_humidity","Humidity"),
         ("sensor.altdorf_temperature","Altdorf"),("sensor.zurich_fluntern_temperature","Zürich")],
   hist=["sensor.altdorf_temperature","sensor.zurich_fluntern_temperature"]),
 dict(key="fohn_coming",group="Weather now",name="Föhn coming",icon="mdi:weather-windy-variant",color="amber",
   tmpl="{{ states('"+FOHN_OUTLOOK+"') in ['south','strong_south'] and states('sensor.altdorf_fohn') != 'foehn' }}",
   secondary="{{ 'Strong south föhn' if is_state('"+FOHN_OUTLOOK+"','strong_south') else 'South föhn' }} likely: {{ states('"+FOHN_DIFF+"') }} hPa more pressure in Lugano than Kloten",
   rule="On when the pressure in Lugano is at least 4 hPa above Kloten's (8 for strong), which drives south föhn, while Altdorf has no föhn yet. It often comes hours before the wind.",
   data=[(FOHN_DIFF,"Lugano − Kloten"),(FOHN_OUTLOOK,"Outlook"),("sensor.altdorf_fohn","Föhn index now")],hist=[FOHN_DIFF]),
 dict(key="gemsstock_open",tmpl="{{ states('sensor.andermatt_gemsstock_status') not in ['Closed','unknown','unavailable',''] }}",group="Mountains",name="Gemsstock open",icon="mdi:gondola",color="green",
   secondary="{{ states('sensor.andermatt_gemsstock_lifts_open_count') }} lifts, {{ states('sensor.andermatt_gemsstock_slopes_open_km') }} km of slopes · Sedrun: {{ states('sensor.andermatt_oberalp_sedrun_status') }}",
   rule="On when Bergfex reports Gemsstock as anything other than closed.",
   data=[("sensor.andermatt_gemsstock_status","Gemsstock"),("sensor.andermatt_gemsstock_lifts_open_count","Lifts open"),("sensor.andermatt_oberalp_sedrun_status","Oberalp – Sedrun")],hist=[]),
 dict(key="snow_down_to_the_pass",tmpl="{% set f = states('sensor.oberalppass_freezing_level')|float(9999) %}{{ f < 2000 }}",group="Mountains",name="Snow to the pass",icon="mdi:snowflake-melt",color="light-blue",
   secondary="Freezing level {{ "+f('sensor.oberalppass_freezing_level')+"|round(0) }} m (Oberalppass 2044 m)",
   rule="On when the forecast freezing level at Oberalppass drops below 2000 m.",
   data=[("sensor.oberalppass_freezing_level","Oberalppass"),("sensor.bristen_freezing_level","Bristen")],hist=["sensor.oberalppass_freezing_level"]),
 dict(key="sun_above_the_fog",tmpl="{% set al_h = states('sensor.altdorf_humidity')|float(0) %}\n{% set al_sun = states('sensor.altdorf_10_minute_sun')|float(10) %}\n{% set an_sun = states('sensor.andermatt_10_minute_sun')|float(0) %}\n{{ is_state('sun.sun','above_horizon') and al_h >= 90 and al_sun == 0 and an_sun >= 5 }}",group="Weather now",name="Sun above the fog",icon="mdi:weather-sunny",color="yellow",
   secondary="Altdorf {{ "+f('sensor.altdorf_humidity')+"|round(0) }} % and grey, Andermatt {{ "+f('sensor.andermatt_10_minute_sun')+"|round(0) }} of 10 min sunny",
   rule="On in daytime when Altdorf is at 90 % humidity or more with no sun, while Andermatt gets at least 5 of every 10 minutes of sun.",
   data=[("sensor.altdorf_humidity","Altdorf humidity"),("sensor.altdorf_10_minute_sun","Altdorf sun (10 min)"),("sensor.andermatt_10_minute_sun","Andermatt sun (10 min)")],hist=[]),
 # --- comfort
 dict(key="close_east_shades",group="Home",name="Close the east shades",icon="mdi:blinds-horizontal",color="amber",
   tmpl="{{ is_state('cover.east_facing_shades','open') and is_state('sun.sun','above_horizon') and 60 <= state_attr('sun.sun','azimuth')|float(0) <= 160 and "+f("sensor.altdorf_sun_irradiation",0)+" > 500 and "+f("sensor.ruuvi_outside_temperature",0)+" > 18 }}",
   secondary="Sun on the east side ({{ states('sensor.altdorf_sun_irradiation')|round(0) }} W/m², {{ states('sensor.ruuvi_outside_temperature')|round(1) }} °C outside)",
   rule="On in the morning (sun azimuth 60–160°) when the east shades are open, irradiance is above 500 W/m² and it's warmer than 18 °C outside.",
   data=[("cover.east_facing_shades","East shades"),("sensor.altdorf_sun_irradiation","Irradiance (Altdorf)"),("sensor.ruuvi_outside_temperature","Outside")],hist=[]),
 dict(key="cooler_outside",group="Home",name="Cooler outside",icon="mdi:window-open-variant",color="teal",
   tmpl="{{ "+f("sensor.ruuvi_kitchen_temperature",0)+" > 24 and "+f("sensor.ruuvi_outside_temperature",99)+" < "+f("sensor.ruuvi_kitchen_temperature",0)+" - 2 and not "+RAINING+" }}",
   secondary="Outside {{ states('sensor.ruuvi_outside_temperature')|round(1) }} °C, kitchen {{ states('sensor.ruuvi_kitchen_temperature')|round(1) }} °C · open the windows",
   rule="On when the kitchen is above 24 °C, it's at least 2 °C cooler outside, and it isn't raining at home (radar).",
   data=[("sensor.ruuvi_outside_temperature","Outside"),("sensor.ruuvi_kitchen_temperature","Kitchen"),(RADAR_RAIN,"Rain rate (radar)")],
   hist=["sensor.ruuvi_outside_temperature","sensor.ruuvi_kitchen_temperature"]),
 # --- calendar & modes
 dict(key="pollen_high",group="Home",name="Pollen high",icon="mdi:flower-pollen",color="lime",
   tmpl=POLLEN_HIGH+"{{ ns.hi | count > 0 }}",
   secondary=POLLEN_HIGH+"Strong in Luzern: {{ ns.hi | join(', ') }} pollen/m³",
   rule="On when a pollen type in Luzern (the station nearest Altdorf) reaches MeteoSwiss's 'strong' class: 70 pollen/m³ for hazel, alder, birch, beech and oak, 50 for grasses, 100 for ash.",
   data=[(POLLEN+"_"+k,k.capitalize()) for k in POLLEN_STRONG],hist=[POLLEN+"_birch",POLLEN+"_grasses"]),
 dict(key="waste_collection",group="Calendar",name="Cardboard pickup",icon="mdi:package-variant-closed",color="brown",
   tmpl="{{ state_attr('"+WASTE+"','message') == 'Karton' and ("+WASTE_DAY+" == "+TOMORROW+" or (is_state('"+WASTE+"','on') and now().hour < 10)) }}",
   secondary="Cardboard {{ 'tomorrow' if "+WASTE_DAY+" == "+TOMORROW+" else 'this morning' }}: put the boxes out",
   rule="On the day before a cardboard (Karton) pickup and on pickup mornings until 10:00. The ZAKU calendar is set to show only Karton (the other types are hidden in the integration's options), and the pill checks for Karton too.",
   data=[(WASTE,"Next cardboard pickup")],hist=[]),
 dict(key="birthday_today",group="Calendar",name="Birthday today",icon="mdi:cake-variant",color="pink",
   tmpl="{{ is_state('calendar.birthdays_2','on') }}",
   secondary="{{ state_attr('calendar.birthdays_2','message') }}",
   rule="On while the Birthdays calendar has an event today.",
   data=[("calendar.birthdays_2","Birthdays")],hist=[]),
 dict(key="holiday_mismatch",group="Calendar",name="Uri and Zürich differ",icon="mdi:calendar-alert",color="purple",
   tmpl="{{ states('"+WORKDAY_UR+"') in ['on','off'] and states('"+WORKDAY_ZH+"') in ['on','off'] and states('"+WORKDAY_UR+"') != states('"+WORKDAY_ZH+"') }}",
   secondary="{{ 'Day off in Uri, but a workday in Zürich' if is_state('"+WORKDAY_UR+"','off') else 'Workday in Uri, but a holiday in Zürich' }}",
   rule="On when today is a workday in one canton and a holiday in the other, e.g. a Catholic holiday in Uri that Zürich doesn't have.",
   data=[(WORKDAY_UR,"Workday in Uri"),(WORKDAY_ZH,"Workday in Zürich")],hist=[]),
 dict(key="holiday_tomorrow",group="Calendar",name="Holiday tomorrow",icon="mdi:party-popper",color="purple",
   tmpl="{{ (state_attr('calendar.holidays_in_switzerland','start_time') or '')[:10] == "+TOMORROW+" }}",
   secondary="{{ state_attr('calendar.holidays_in_switzerland','message') }}",
   rule="On the day before an event in the Swiss holidays calendar (this calendar also lists clock changes).",
   data=[("calendar.holidays_in_switzerland","Swiss holidays")],hist=[]),
 dict(key="on_vacation",group="Calendar",name="On vacation",icon="mdi:palm-tree",color="green",
   tmpl="{{ is_state('calendar.copebit_vacations_vacation_calendar','on') and 'Jan' in (state_attr('calendar.copebit_vacations_vacation_calendar','message') or '') }}",
   secondary="{{ state_attr('calendar.copebit_vacations_vacation_calendar','message') }}",
   rule="On while the copebit vacation calendar has an entry with 'Jan' in its title (it also lists colleagues).",
   data=[("calendar.copebit_vacations_vacation_calendar","copebit vacations")],hist=[]),
 dict(key="guests",group="Calendar",name="Guests",icon="mdi:account-group",color="purple",
   tmpl="{{ is_state('input_boolean.guest_mode','on') }}",secondary="Guest mode is on",
   rule="On while guest mode is on.",data=[("input_boolean.guest_mode","Guest mode")],hist=[]),
 dict(key="cleaning",group="Calendar",name="Cleaning mode",icon="mdi:broom",color="brown",
   tmpl="{{ is_state('input_boolean.cleaning_mode','on') }}",secondary="Cleaning mode is on",
   rule="On while cleaning mode is on.",data=[("input_boolean.cleaning_mode","Cleaning mode")],hist=[]),
 dict(key="record_player_open",group="Home",name="Record player open",icon="mdi:album",color="deep-purple",
   tmpl="{{ is_state('binary_sensor.aqara_record_player','on') }}",
   secondary="Open since {{ states.binary_sensor.aqara_record_player.last_changed | as_local | relative_time }}",
   rule="On while the record player's sensor reports it open.",
   data=[("binary_sensor.aqara_record_player","Record player")],hist=[]),
 dict(key="reussdelta_swim",group="Rivers",name="Swim day at the Reussdelta",icon="mdi:swim",color="teal",
   tmpl="{{ states('"+REUSS+"_temperature')|float(0) >= 18 and states('weather.altdorf_ur') in ['sunny','partlycloudy','clear-night'] and is_state('sun.sun','above_horizon') }}",
   secondary="Reuss {{ states('"+REUSS+"_temperature') }} °C at Seedorf, {{ states('sensor.altdorf_temperature') }} °C in Altdorf",
   rule="On in daylight when the Reuss at Seedorf is 18 °C or warmer and Altdorf is sunny.",
   data=[(REUSS+"_temperature","Reuss water"),("sensor.altdorf_temperature","Altdorf air")],hist=[REUSS+"_temperature"]),
 dict(key="glacier_melt",group="Rivers",name="Glacier melt",icon="mdi:snowflake-melt",color="light-blue",
   tmpl="{{ states('"+GLETSCH+"')|float(0) >= 15 }}",
   secondary="Rhône at Gletsch {{ states('"+GLETSCH+"')|float(0)|round(1) }} m³/s (July mean 9, record 56)",
   rule="On when the Rhône at Gletsch, right below the Rhône glacier, carries 15 m³/s or more: a hot spell at altitude.",
   data=[(GLETSCH,"Rhône at Gletsch")],hist=[GLETSCH]),
 dict(key="muddy_paths",group="Rivers",name="Muddy paths",icon="mdi:shoe-print",color="brown",
   tmpl="{{ states('"+RAIN_24H+"')|float(0) >= 10 }}",
   secondary="{{ states('"+RAIN_24H+"')|float(0)|round(1) }} mm of rain in Altdorf over the last 24 h",
   rule="On when Altdorf has measured 10 mm of rain or more over the last 24 hours (a Statistics helper sums the 10-minute rain).",
   data=[(RAIN_24H,"Rain 24 h"),("sensor.altdorf_10_minute_rain","Rain 10 min")],hist=[RAIN_24H]),
 dict(key="plane_overhead",group="Home",name="Plane overhead",icon="mdi:airplane",color="light-blue",
   tmpl="{{ "+FLIGHTS+" | count > 0 }}",
   secondary="{% set fl = "+FLIGHTS+" %}{% if fl %}{% set f = fl[0] %}{{ f.callsign or f.aircraft_registration }} · {{ f.aircraft_model }} at {{ (f.altitude|float(0) * 0.3048)|round(-2)|int }} m, {{ f.distance|round(1) }} km away · {{ f.airport_origin_city or '?' }} → {{ f.airport_destination_city or '?' }}{% else %}Nothing within 3 km{% endif %}",
   rule="On while FlightRadar24 sees an aircraft within 3 km of home.",
   data=[("sensor.flightradar24_current_in_area","Aircraft in area"),("sensor.flightradar24_entered_area","Entered area")],hist=["sensor.flightradar24_current_in_area"]),
 # --- maintenance
 dict(key="storage_full",group="Proxmox",name="Storage filling up",icon="mdi:harddisk",color="orange",
   tmpl=FULL_STORAGES+"{{ ns.f | count > 0 }}",
   secondary=FULL_STORAGES+"{{ ns.f | join(', ') }}",
   summary=STORAGE_TABLE,
   rule="On when a Proxmox storage is more than 85 % full.",
   data=[("sensor.5_storage_schmatzdata_usage","schmatzdata (NFS)"),("sensor.5_storage_local_lvm_usage","local-lvm"),("sensor.5_storage_local_usage","local")],
   hist=["sensor.5_storage_schmatzdata_usage"]),
 dict(key="router_hot",group="Maintenance",name="Router running hot",icon="mdi:thermometer-high",color="orange",
   tmpl="{{ states('sensor.schmatzrouter_cpu_temperature_2')|float(0) > 85 }}",
   secondary="CPU at {{ states('sensor.schmatzrouter_cpu_temperature_2')|round(0) }} °C, {{ states('sensor.schmatzrouter_cpu_utilization_2')|round(0) }} % busy",
   rule="On when the UniFi router's CPU is above 85 °C.",
   data=[("sensor.schmatzrouter_cpu_temperature_2","CPU temperature"),("sensor.schmatzrouter_cpu_utilization_2","CPU load"),("sensor.schmatzrouter_memory_utilization_2","Memory")],
   hist=["sensor.schmatzrouter_cpu_temperature_2"]),
 dict(key="router_restarted",group="Maintenance",name="Router restarted",icon="mdi:router-network",color="blue-grey",
   tmpl="{{ states('sensor.schmatzrouter_uptime_2') not in ['unknown','unavailable'] and now() - as_datetime(states('sensor.schmatzrouter_uptime_2')) < timedelta(hours=1) }}",
   secondary="Up since {{ (states('sensor.schmatzrouter_uptime_2')|as_datetime|as_local).strftime('%H:%M') if states('sensor.schmatzrouter_uptime_2') not in ['unknown','unavailable'] }}",
   rule="On for the first hour after the UniFi router restarts.",
   data=[("sensor.schmatzrouter_uptime_2","Up since"),("sensor.schmatzrouter_state","State"),("sensor.quagmire_clients","Clients on quagmire")],hist=[]),
 dict(key="server_stressed",group="Proxmox",name="Server stressed",icon="mdi:server-network",color="red",
   tmpl="{{ ['binary_sensor.overloaded','binary_sensor.disk_overloaded','binary_sensor.stressed'] | select('is_state','on') | list | count > 0 }}",
   secondary="Proxmox: {{ ['binary_sensor.overloaded','binary_sensor.disk_overloaded','binary_sensor.stressed'] | select('is_state','on') | map('state_attr','friendly_name') | join(', ') }}",
   rule="On when Proxmox reports the node overloaded, its disks overloaded, or stressed.",
   data=[("binary_sensor.overloaded","Overloaded"),("binary_sensor.disk_overloaded","Disk overloaded"),("binary_sensor.stressed","Stressed"),(PROX+"_io_wait","IO wait")],hist=[]),
 dict(key="server_hot",group="Proxmox",name="Server running hot",icon="mdi:thermometer-high",color="red",
   tmpl="{{ states('"+PROX+"_cpu_temperature')|float(0) > 80 }}",
   secondary="CPU at {{ states('"+PROX+"_cpu_temperature')|round(0)|int }} °C, {{ states('"+PROX+"_cpu_usage')|round(0)|int }} % busy · NVMe {{ states('"+PROX+"_micron_mtfdkcd1t0tfk_953gb')|round(0)|int }} °C",
   rule="On when the Proxmox host's CPU is above 80 °C.",
   data=[(PROX+"_cpu_temperature","CPU temperature"),(PROX+"_cpu_usage","CPU usage"),(PROX+"_micron_mtfdkcd1t0tfk_953gb","NVMe temperature")],
   hist=[PROX+"_cpu_temperature"]),
 dict(key="server_swapping",group="Proxmox",name="Server swapping",icon="mdi:memory",color="orange",
   tmpl="{{ states('"+PROX+"_swap_usage')|float(0) > 50 }}",
   secondary="Swap {{ states('"+PROX+"_swap_usage')|round(0)|int }} % used, memory {{ states('"+PROX+"_memory_usage')|round(0)|int }} %",
   rule="On when the Proxmox host uses more than half its swap: it's short of memory (16 GB) and slowing down.",
   data=[(PROX+"_swap_usage","Swap"),(PROX+"_memory_usage","Memory")],
   hist=[PROX+"_swap_usage",PROX+"_memory_usage"]),
 dict(key="server_monitoring",group="Proxmox",name="Proxmox monitoring incomplete",icon="mdi:server-off",color="orange",
   tmpl="{{ states('"+PROX+"_sidecar_status') in ['error','degraded'] or state_attr('"+PROX+"_node_status','pve_version') in ['unknown', None] }}",
   secondary="Sidecar {{ states('"+PROX+"_sidecar_status') }}{{ ' · no node details (API permissions?)' if state_attr('"+PROX+"_node_status','pve_version') in ['unknown', None] }}",
   rule="On when the Proxmox sidecar reports an error, or the API can't read the node's details: then the other Proxmox pills can't see anything.",
   data=[(PROX+"_sidecar_status","Sidecar"),(PROX+"_node_status","Node")],hist=[]),
 dict(key="server_backup",group="Proxmox",name="Proxmox backup running",icon="mdi:database-sync",color="blue-grey",
   tmpl="{{ states('"+PROX+"_backup_progress') not in ['idle','unknown','unavailable',''] }}",
   secondary="Backup: {{ states('"+PROX+"_backup_progress') }} · last task {{ states('"+PROX+"_last_task') }}",
   rule="On while a Proxmox backup runs.",
   data=[(PROX+"_backup_progress","Backup"),(PROX+"_last_task","Last task")],hist=[]),
 dict(key="server_updates",group="Proxmox",name="Proxmox updates",icon="mdi:package-up",color="grey",
   tmpl="{{ states('"+PROX+"_node_updates')|int(0) > 0 }}",
   secondary="{{ states('"+PROX+"_node_updates') }} package updates on prox",
   rule="On when the Proxmox node has package updates waiting.",
   data=[(PROX+"_node_updates","Updates")],hist=[]),
 dict(key="low_batteries",group="Maintenance",name="Low batteries",icon="mdi:battery-alert-variant-outline",color="orange",
   tmpl=LOWBAT+"{{ low|count + crit|count > 0 }}",
   secondary=LOWBAT_LIST,
   summary=LOWBAT_LIST,
   rule="On when any battery (phones excluded) is below 20 %, or a device reports its battery as critical.",
   data=[("sensor.aqara_fridge_temp_battery","Fridge thermometer"),("sensor.lumi_lumi_vibration_aq1_battery","Vibration sensor"),
         ("sensor.entrance_button_battery","Entrance button"),("sensor.hallway_tablet_battery_level","Hallway tablet"),("sensor.nuki_schmatzknauf_battery_2","Nuki lock")],hist=[]),
 dict(key="updates_waiting",group="Maintenance",name="Updates waiting",icon="mdi:package-up",color="grey",
   tmpl="{{ "+UPDATES+" | count > 0 }}",
   secondary="{{ "+UPDATES+" | count }} available: {{ "+UPDATES+" | map(attribute='name') | join(', ') }}",
   summary="{{ "+UPDATES+" | map(attribute='name') | join(', ') or 'Everything is up to date.' }}",
   rule="On when any update entity has an update available.",
   data=[],hist=[]),
 dict(key="record_warm",group="Climate",name="Record warm",icon="mdi:thermometer-chevron-up",color="red",
   tmpl="{{ "+HIGH+" is number and "+HIGH+" >= states('"+RECORD+"')|float(99) }}",
   secondary="{{ "+HIGH+" }} °C in Altdorf today, record for the date {{ states('"+RECORD+"') }} °C ({{ state_attr('"+RECORD+"','year') }})",
   rule="On when today's high in Altdorf reaches the record for the date (records since 1864).",
   data=[(CLIM+"_high_vs_normal","High vs normal"),(RECORD,"Record high")],hist=[]),
 dict(key="record_cold",group="Climate",name="Record cold",icon="mdi:thermometer-chevron-down",color="blue",
   tmpl="{{ "+LOW+" is number and "+LOW+" <= state_attr('"+RECORD+"','record_low')|float(-99) }}",
   secondary="{{ "+LOW+" }} °C in Altdorf, record low for the date {{ state_attr('"+RECORD+"','record_low') }} °C ({{ state_attr('"+RECORD+"','record_low_year') }})",
   rule="On when today's low in Altdorf reaches the record low for the date.",
   data=[(CLIM+"_low_vs_normal","Low vs normal"),(RECORD,"Record high (record low in details)")],hist=[]),
 dict(key="unusually_warm",group="Climate",name="Unusually warm",icon="mdi:thermometer-plus",color="orange",
   tmpl="{{ states('"+CLIM+"_high_vs_normal')|float(0) >= 6 }}",
   secondary="{{ "+HIGH+" }} °C, {{ '%+.1f'|format(states('"+CLIM+"_high_vs_normal')|float(0)) }} °C against the normal high of {{ state_attr('"+CLIM+"_high_vs_normal','normal_high') }} °C",
   rule="On when today's high in Altdorf is at least 6 °C above the 1991–2020 normal for the date.",
   data=[(CLIM+"_high_vs_normal","High vs normal")],hist=[CLIM+"_high_vs_normal"]),
 dict(key="unusually_cold",group="Climate",name="Unusually cold",icon="mdi:thermometer-minus",color="light-blue",
   tmpl="{{ states('"+CLIM+"_high_vs_normal')|float(0) <= -6 }}",
   secondary="{{ "+HIGH+" }} °C, {{ '%+.1f'|format(states('"+CLIM+"_high_vs_normal')|float(0)) }} °C against the normal high of {{ state_attr('"+CLIM+"_high_vs_normal','normal_high') }} °C",
   rule="On when today's high in Altdorf is at least 6 °C below the 1991–2020 normal for the date.",
   data=[(CLIM+"_high_vs_normal","High vs normal")],hist=[CLIM+"_high_vs_normal"]),
 dict(key="warm_night",group="Climate",name="Warm night",icon="mdi:weather-night",color="deep-purple",
   tmpl="{{ states('"+CLIM+"_low_vs_normal')|float(0) >= 6 }}",
   secondary="Low of {{ "+LOW+" }} °C, {{ '%+.1f'|format(states('"+CLIM+"_low_vs_normal')|float(0)) }} °C against the normal low of {{ state_attr('"+CLIM+"_low_vs_normal','normal_low') }} °C",
   rule="On when the night's low in Altdorf is at least 6 °C above normal (föhn nights often are).",
   data=[(CLIM+"_low_vs_normal","Low vs normal")],hist=[CLIM+"_low_vs_normal"]),
 dict(key="dog_walk_good",group="Rivers",name="Good time for a dog walk",icon="mdi:dog",color="green",
   tmpl="{% set q = states('"+REUSS+"_discharge') %}{{ is_state('sun.sun','above_horizon') and q not in ['unknown','unavailable'] and q|float(0) < states('"+REUSS_LIMIT+"')|float(0) and states('sensor.altdorf_ur_chance_of_rain_next_hour')|float(100) < 40 and not "+RAINING+" and 'wind' not in (state_attr('sensor.altdorf_ur_weather_warning','types') or []) and not is_state('binary_sensor.pill_lightning_nearby','on') and states('"+RAIN_24H+"')|float(0) < 10 }}",
   secondary="Reuss {{ states('"+REUSS+"_discharge')|float(0)|round(0)|int }} m³/s (limit {{ states('"+REUSS_LIMIT+"')|int }}), {{ states('sensor.altdorf_ur_chance_of_rain_next_hour')|round(0)|int }} % chance of rain in the next hour, no wind warning",
   rule="On in daylight when the Reuss is below your limit, rain in the next hour is unlikely (under 40 %) and it isn't raining now (radar), there's no wind warning or lightning nearby, and the paths aren't muddy.",
   data=[(REUSS+"_discharge","Reuss"),(REUSS_LIMIT,"Your limit"),("sensor.altdorf_ur_chance_of_rain_next_hour","Rain next hour"),(RADAR_RAIN,"Rain now (radar)"),(RAIN_24H,"Rain 24 h")],hist=[]),
 dict(key="big_load",group="Home",name="Big load",icon="mdi:flash-alert",color="yellow",
   tmpl="{{ states('sensor.apartment_consumption_total_active_power')|float(0) > 1500 }}",
   secondary="{{ states('sensor.apartment_consumption_total_active_power')|round(0) }} W right now (usually around 260 W)",
   rule="On while the apartment draws more than 1.5 kW. Over a normal 10 days it peaks at about 1.6 kW.",
   data=[("sensor.apartment_consumption_total_active_power","Total power"),("sensor.apartment_consumption_phase_a_active_power","Phase A"),
         ("sensor.apartment_consumption_phase_b_active_power","Phase B"),("sensor.apartment_consumption_phase_c_active_power","Phase C")],
   hist=["sensor.apartment_consumption_total_active_power"]),
 dict(key="now_playing",group="Home",name="Now playing",icon="mdi:music",color="green",
   tmpl="{{ "+PLAYING+" | count > 0 }}",
   secondary="{% for p in "+PLAYING+" %}{{ p.attributes.media_title or 'Something' }}{{ ' – ' ~ p.attributes.media_artist if p.attributes.media_artist }} ({{ p.name }}){{ ' · ' if not loop.last }}{% endfor %}",
   rule="On while a Sonos speaker or Spotify is playing.",
   data=[(m,n) for m,n in zip(PLAYERS,["Living Room","Madagascar","Living Room (2)","Spotify"])],hist=[]),
 month_pill("dry_month","Dry month","mdi:water-off","brown",RAIN_PCT+" < 30",MONTH_TEXT,"On when Altdorf has had less than 30 % of the month's normal rain."),
 month_pill("wet_month","Wet month","mdi:weather-pouring","blue",RAIN_PCT+" > 200",MONTH_TEXT,"On when Altdorf has had more than twice the month's normal rain."),
 month_pill("sunny_month","Sunny month","mdi:white-balance-sunny","yellow",SUN_PCT+" > 150",MONTH_TEXT,"On when Altdorf has had more than 150 % of the month's normal sunshine."),
 month_pill("grey_month","Grey month","mdi:weather-cloudy","grey",SUN_PCT+" < 50",MONTH_TEXT,"On when Altdorf has had less than half the month's normal sunshine."),
 month_pill("warm_month","Warm month","mdi:trending-up","orange",MONTH_T+" >= 2",MONTH_TEXT,"On when the month in Altdorf is running at least 2 °C warmer than normal."),
 dict(key="trains_today",group="Travel",name="Trains today",icon="mdi:train",color="green",
   tmpl="{{ states('"+TRAINS_TODAY+"')|int(0) > 0 }}",
   content="{{ states('"+TRAINS_TODAY+"')|int(0) }}",
   secondary="{{ states('"+TRAINS_TODAY+"')|int(0) }} trains past the window since midnight"
             "{{ ' · one on the track now' if is_state('"+TRAIN_PASSING+"','on') }}",
   rule="On from the first train of the day; the row shows the count. A train counts when Frigate sees it in the track zone of the full-resolution crop camera, and one that drops out for under 30 s still counts once.",
   data=[(TRAINS_TODAY,"Trains today"),(TRAIN_PASSING,"Train passing"),(TRAIN_ON_TRACK,"Frigate: train on the track")],
   hist=[TRAIN_PASSING]),
 month_pill("cold_month","Cold month","mdi:trending-down","light-blue",MONTH_T+" <= -2",MONTH_TEXT,"On when the month in Altdorf is running at least 2 °C colder than normal."),
]
GROUPS=["Safety","Kitchen","Travel","Rivers","Forecast","Weather now","Mountains","Home","Calendar","Climate","Proxmox","Maintenance"]
