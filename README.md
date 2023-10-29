# hass-comapsmarthome
A Home Assistant custom component for comap smart home thermostats (qivivo)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rbiremon&repository=hass-comapsmarthome)

## Supported features
This is designed for Qivivo Fil Pilote thermostats.

It will set up one sensor for the main housing, and climate entities for each zone.

* Multi-zone support
* Thermostat zone: set temperature, current temperature and humidity
* Pilot wire zone: set preset mode
* Set home away, home back for housing
* Set schedule for a given zone (list of schedules is available under housing sensor)

Does not support:

* Mulitple housings
* Multiple programs (a program is a set of schedules to apply to your different zones)
* Other type of Comap thermal devices than pilot wire

## Current limitations

* Polling interval is not customizable
* Any manual instruction is set for 2 hours by default
* Your applied schedule will cancel any temporary orders - this is Comap behavior


## Configuration

You can deploy the component to custom_components directory in you home assistant config directory, or use HACS by pointing to this repository.

Setup through the Home Assistant Integration menu - you will need your Comap username and password.

