#!/usr/bin/env python3
""" tala - Teams Audit Log Analyzer
Licence: BSD 3 clauses (see https://opensource.org/licenses/BSD-3-Clause)
Auteur: Hubert Tournier
"""

import csv
import datetime
import getopt
import json
import logging
import os
import pprint
import re
import signal
import sys

# Chaîne de version utilisée par les commandes what(1) et ident(1) :
ID = "@(#) $Id: tala - Teams Audit Log Analyzer v3.0.0 (12 Avril 2024) par Hubert Tournier $"

# Paramètres par défaut. Peuvent être redéfinis via la ligne de commande
parametres = {
    "Afficher contenu": True,
    "Lister organisateurs": False,
    "Lister participants": False,
    "Lister deconnexions": False,
    "Base utilisateurs": "",
    "Filtre adresses": None,
}

DELIMITER = ","

################################################################################
def _initialisation_journalisation(nom_programme):
    """ Configuration de la journalisation """
    format_journal = nom_programme + ": %(levelname)s: %(message)s"
    logging.basicConfig(format=format_journal, level=logging.DEBUG)
    logging.disable(logging.INFO)

################################################################################
def _afficher_aide():
    """ Afficher le mode opératoire """
    print(file=sys.stderr)
    print("usage: tala [--debug] [--help|-?] [--version]", file=sys.stderr)
    print("       [-o|--organizers] [-a|--attendees]", file=sys.stderr)
    print("       [-u|--users FILE]", file=sys.stderr)
    print("       [-d|--disconnect] [-i|--ip REGEX]", file=sys.stderr)
    print("       [--] [file ...]", file=sys.stderr)
    print(
        "  ---------------  -------------------------------------------------",
        file=sys.stderr
    )
    print("  -o|--organizers  List meetings organizers", file=sys.stderr)
    print("  -a|--attendees   List meetings attendees", file=sys.stderr)
    print("  -d|--disconnect  List meetings disconnections", file=sys.stderr)
    print("  -i|--ip REGEX    Filter meeting disconnections by IP address regex", file=sys.stderr)
    print("  -u|--users FILE  create/update and use the FILE users database", file=sys.stderr)
    print("  --debug          Enable debug mode", file=sys.stderr)
    print("  --help|-?        Print usage and this help message and exit", file=sys.stderr)
    print("  --version        Print version and exit", file=sys.stderr)
    print("  --               Options processing terminator", file=sys.stderr)
    print(file=sys.stderr)

################################################################################
def _gestion_controle_c(signal_number, current_stack_frame):
    """ Ne pas afficher de stack trace sur contrôle-C """
    print(" Interrupted!\n", file=sys.stderr)
    _afficher_aide()
    sys.exit(1)

################################################################################
def _gestion_signaux():
    """ Gestion des signaux """
    signal.signal(signal.SIGINT, _gestion_controle_c)

################################################################################
def _gestion_ligne_commande():
    """ Gestion des arguments passés sur la ligne de commande """
    # pylint: disable=C0103
    global parametres
    # pylint: enable=C0103

    # Options reconnues :
    lettres_options = "adi:ou:?"
    chaines_options = [
        "attendees",
        "debug",
        "disconnect",
        "help",
        "ip=",
        "organizers",
        "users=",
        "version",
    ]

    try:
        options, arguments_restants = getopt.getopt(
            sys.argv[1:], lettres_options, chaines_options
        )
    except getopt.GetoptError as erreur:
        logging.critical("Syntax error: %s", erreur)
        _afficher_aide()
        sys.exit(1)

    for option, argument in options:

        if option in ("-a", "--attendees"):
            parametres["Afficher contenu"] = False
            parametres["Lister organisateurs"] = False
            parametres["Lister participants"] = True
            parametres["Lister deconnexions"] = False

        elif option in ("-d", "--disconnect"):
            parametres["Afficher contenu"] = False
            parametres["Lister organisateurs"] = False
            parametres["Lister participants"] = False
            parametres["Lister deconnexions"] = True

        elif option in ("-i", "--ip"):
            try:
                parametres["Filtre adresses"] = re.compile(argument)
            except:
                logging.critical("'%s' is not a regular expression", argument)
                sys.exit(1)

        elif option in ("-o", "--organizers"):
            parametres["Afficher contenu"] = False
            parametres["Lister organisateurs"] = True
            parametres["Lister participants"] = False
            parametres["Lister deconnexions"] = False

        elif option in ("-u", "--users"):
            parametres["Base utilisateurs"] = argument

        elif option == "--debug":
            logging.disable(logging.NOTSET)

        elif option in ("--help", "-?"):
            _afficher_aide()
            sys.exit(0)

        elif option == "--version":
            print(ID.replace("@(" + "#)" + " $" + "Id" + ": ", "").replace(" $", ""))
            sys.exit(0)

    return arguments_restants

################################################################################
def convertir_secondes(chaine):
    """ Retourne le nombre de secondes écoulées depuis l'Epoch à partir d'une chaîne de date """
    return datetime.datetime.strptime(chaine, "%Y-%m-%dT%H:%M:%S").timestamp()

################################################################################
def extraire_reunions(fichier, afficher):
    """ Retourne des structures contenant la liste des réunions/organisateurs et des participants
        Vérifie au passage la présence de valeurs inhabituelles dans les champs """
    organisateurs = {}
    participants = {}

    numero_ligne = 1
    lignes = csv.DictReader(fichier, delimiter=DELIMITER)
    for ligne in lignes:
        if ligne["Operation"] != "MeetingParticipantDetail":
            logging.warning(f"Ligne {numero_ligne} : 'Operation' différent de 'MeetingParticipantDetail' : {ligne['Operation']}")

        details = json.loads(ligne["AuditData"])

        if afficher:
            print(f"Line #{numero_ligne}")
            print(f"CreationDate={ligne['CreationDate']}")
            print(f"UserId={ligne['UserId']}")
            print(f"Operation={ligne['Operation']}")
            print("AuditData:")
            pprint.pprint(details, compact=False, sort_dicts=False)
            if "Operation" in details and details["Operation"] != "MeetingParticipantDetail":
                logging.info(f"Ligne {numero_ligne} : 'Operation' différent de 'MeetingParticipantDetail': {details['Operation']}")
            if "Workload" in details and details["Workload"] != "MicrosoftTeams":
                logging.info(f"Ligne {numero_ligne} : 'Workload' différent de 'MicrosoftTeams': {details['Workload']}")
            if "ArtifactSharedName" in details and details["ArtifactSharedName"] != "videoTransmitted":
                logging.info("Ligne {numero_ligne} : 'ArtifactSharedName' différent de 'videoTransmitted': {details['ArtifactSharedName']}")
            if "Key" in details and details["Key"] != "UserAgent":
                logging.info(f"Ligne {numero_ligne} : 'Key' différent de 'UserAgent': {details['Key']}")
            if "RecipientType" in details and details["RecipientType"] not in ("User", "Anonymous", "Applications", "Phone"):
                logging.info(f"Ligne {numero_ligne} : 'RecipientType' différent des valeurs connues: {details['RecipientType']}")
            if "ItemName" in details and details["ItemName"] not in ("ScheduledMeeting", "RecurringMeeting", "Escalation", "AdHocMeeting", "ChannelMeeting", "MicrosoftTeams", "Complete", "Broadcast", "ScreenSharingCall", "31"):
                logging.info(f"Ligne {numero_ligne} : 'ItemName' différent des valeurs connues: {details['ItemName']}")
            if "RecordType" in details and details["RecordType"] != 25:
                logging.info(f"Ligne {numero_ligne} : 'RecordType' différent de 25: {details['RecordType']}")
            if "UserType" in details and details["UserType"] != 0:
                logging.info(f"Ligne {numero_ligne} : 'UserType' différent de 0: {details['UserType']}")
            if "Version" in details and details["Version"] != 1:
                logging.info(f"Ligne {numero_ligne} : 'Version' différent de 1: {details['Version']}")
            print()

        id_reunion = ""
        if "MeetingDetailId" in details:
            id_reunion = details["MeetingDetailId"]
        else:
            logging.warning(f"Ligne {numero_ligne} : 'MeetingDetailId' absent")

        email_organisateur = ""
        if "UserId" in details:
            email_organisateur = details["UserId"]
        else:
            logging.info(f"Ligne {numero_ligne} : 'UserId' absent")

        id_organisateur = ""
        if "UserKey" in details:
            id_organisateur = details["UserKey"]
        else:
            logging.info(f"Ligne {numero_ligne} : 'UserKey' absent")

        id_organisation_organisateur = ""
        if "OrganizationId" in details:
            id_organisation_organisateur = details["OrganizationId"]
        else:
            logging.info(f"Ligne {numero_ligne} : 'OrganizationId' absent")

        type_reunion = ""
        if "ItemName" in details:
            type_reunion = details["ItemName"]
        else:
            logging.info(f"Ligne {numero_ligne} : 'ItemName' absent")

        type_cle = ""
        id_participant = ""
        libelle_participant = ""
        cle_participant = ""
        id_organisation_participant = ""
        if "Attendees" in details:
            if len(details["Attendees"]) == 1:
                if "RecipientType" in details["Attendees"][0]:
                    type_cle = details["Attendees"][0]["RecipientType"]
                else:
                    type_cle = "?"

                if "UserObjectId" in details["Attendees"][0]:
                    id_participant = details["Attendees"][0]["UserObjectId"]
                    cle_participant = id_participant

                    if "OrganizationId" in details["Attendees"][0]:
                        id_organisation_participant = details["Attendees"][0]["OrganizationId"]

                elif "DisplayName" in details["Attendees"][0]:
                    libelle_participant = details["Attendees"][0]["DisplayName"].replace(DELIMITER, " ")
                    cle_participant = libelle_participant
                else:
                    logging.warning(f"Ligne {numero_ligne} : 'Attendees/UserObjectid' et 'Attendees/DisplayName' absents")
            else:
                logging.warning(f"Ligne {numero_ligne} : 'Attendees' contient plus de {len(details['Attendees'])} participants au lieu de 1")
        else:
            logging.warning(f"Ligne {numero_ligne} : 'Attendees' absent")

        propriete = ""
        if "ExtraProperties" in details:
            if "Value" in details["ExtraProperties"]:
                propriete = details["ExtraProperties"]["Value"]
                propriete = re.sub(r" \(.*", "", propriete)
                propriete = re.sub(r"SkypeSpaces.*", "SkypeSpaces", propriete)
                propriete = re.sub(r"^[0-9].*", "Some Agent", propriete)

        debut = ""
        if "JoinTime" in details:
            debut = details["JoinTime"]
        else:
            logging.warning(f"Ligne {numero_ligne} : 'JoinTime' absent")

        fin = ""
        if "LeaveTime" in details:
            fin = details["LeaveTime"]
        else:
            logging.warning(f"Ligne {numero_ligne} : 'LeaveTime' absent")

        adresse_ip = ""
        if "ClientIP" in details:
            adresse_ip = details["ClientIP"]
        else:
            logging.info(f"Ligne {numero_ligne} : 'ClientIP' absent")

        materiel = ""
        if "DeviceInformation" in details:
            materiel = details["DeviceInformation"].replace(DELIMITER, " ")
        else:
            logging.info(f"Ligne {numero_ligne} : 'DeviceInformation' absent")

        if id_reunion in organisateurs:
            if email_organisateur != organisateurs[id_reunion]["email_organisateur"]:
                logging.warning(f"Ligne {numero_ligne} : 'email_organisateur' modifié")
            if id_organisateur != organisateurs[id_reunion]["id_organisateur"]:
                logging.warning(f"Ligne {numero_ligne} : 'id_organisateur' modifié")
            if id_organisation_organisateur != organisateurs[id_reunion]["id_organisation"]:
                logging.warning(f"Ligne {numero_ligne} : 'id_organisation_organisateur' modifié")
            # le type de réunion est différent pour les personnes invitées en cours de réunion
            #if type_reunion != organisateurs[id_reunion]["type_reunion"]:
            #    logging.warning(f"Ligne {numero_ligne} : 'type_reunion' modifié pour la réunion")
            secondes = convertir_secondes(debut)
            if secondes < 0:
                logging.error(f"Ligne {numero_ligne} : 'debut' incorrect: {debut}")
            elif secondes < convertir_secondes(organisateurs[id_reunion]["premier_arrive"]):
                organisateurs[id_reunion]["premier_arrive"] = debut
            secondes = convertir_secondes(fin)
            if secondes < 0:
                logging.error(f"Ligne {numero_ligne} : 'fin' incorrect: {fin}")
            elif secondes > convertir_secondes(organisateurs[id_reunion]["dernier_parti"]):
                organisateurs[id_reunion]["dernier_parti"] = fin
            if cle_participant not in organisateurs[id_reunion]["participants"]:
                organisateurs[id_reunion]["participants"].append(cle_participant)
        else:
            # Nouvelle réunion
            details_reunion = {}
            details_reunion["email_organisateur"] = email_organisateur
            details_reunion["id_organisateur"] = id_organisateur
            details_reunion["id_organisation"] = id_organisation_organisateur
            details_reunion["type_reunion"] = type_reunion
            details_reunion["premier_arrive"] = debut
            details_reunion["dernier_parti"] = fin
            details_reunion["participants"] = [cle_participant]
            organisateurs[id_reunion] = details_reunion

        if id_reunion in participants:
            if cle_participant in participants[id_reunion]:
                i = 0
                doublon = False
                while i < len(participants[id_reunion][cle_participant]):
                    if debut == participants[id_reunion][cle_participant][i]["debut"] \
                    and fin == participants[id_reunion][cle_participant][i]["fin"] \
                    and adresse_ip == participants[id_reunion][cle_participant][i]["adresse_ip"] \
                    and materiel == participants[id_reunion][cle_participant][i]["materiel"] \
                    and propriete == participants[id_reunion][cle_participant][i]["propriete"] \
                    and type_cle == participants[id_reunion][cle_participant][i]["type_cle"] \
                    and id_organisation_participant == participants[id_reunion][cle_participant][i]["id_organisation"]:
                        doublon = True
                        break

                    # On va trier les connexions par heure de début, puis par heure de fin :
                    secondes_debut_nouveau = convertir_secondes(debut)
                    secondes_debut_element = convertir_secondes(participants[id_reunion][cle_participant][i]["debut"])
                    if secondes_debut_nouveau < secondes_debut_element:
                        break
                    if secondes_debut_nouveau == secondes_debut_element:
                        secondes_fin_nouveau = convertir_secondes(fin)
                        secondes_fin_element = convertir_secondes(participants[id_reunion][cle_participant][i]["fin"])
                        if secondes_fin_nouveau <= secondes_fin_element:
                            break

                    i += 1

                if not doublon:
                    # Nouvelle connexion du participant à la réunion
                    details_connexion = {}
                    details_connexion["type_cle"] = type_cle
                    details_connexion["id_organisation"] = id_organisation_participant
                    details_connexion["debut"] = debut
                    details_connexion["fin"] = fin
                    details_connexion["adresse_ip"] = adresse_ip
                    details_connexion["materiel"] = materiel
                    details_connexion["propriete"] = propriete

                    # insertion triée :
                    participants[id_reunion][cle_participant] = participants[id_reunion][cle_participant][:i] \
                                                                + [details_connexion] \
                                                                +  participants[id_reunion][cle_participant][i:]
            else:
                # Nouveau participant à la réunion
                details_connexion = {}
                details_connexion["type_cle"] = type_cle
                details_connexion["id_organisation"] = id_organisation_participant
                details_connexion["debut"] = debut
                details_connexion["fin"] = fin
                details_connexion["adresse_ip"] = adresse_ip
                details_connexion["materiel"] = materiel
                details_connexion["propriete"] = propriete
                participants[id_reunion][cle_participant] = [details_connexion]
        else:
            # Nouvelle réunion
            details_connexion = {}
            details_connexion["type_cle"] = type_cle
            details_connexion["id_organisation"] = id_organisation_participant
            details_connexion["debut"] = debut
            details_connexion["fin"] = fin
            details_connexion["adresse_ip"] = adresse_ip
            details_connexion["materiel"] = materiel
            details_connexion["propriete"] = propriete
            participant = {cle_participant: [details_connexion]}
            participants[id_reunion] = participant

        numero_ligne += 1

    return organisateurs, participants

################################################################################
def charger_uids(nom_fichier):
    """ Construit un dictionnaire UID: EMAIL à partir d'un fichier CSV UID,EMAIL """
    uids = {}

    if not os.path.isfile(nom_fichier):
        with open(nom_fichier, "w", encoding="utf-8") as fichier:
            pass

    with open(nom_fichier, "r", encoding="utf-8") as fichier:
        for ligne in fichier.readlines():
            champs = ligne.strip().split(",")
            uids[champs[0]] = champs[1]
    return uids

################################################################################
def mettre_a_jour_uids(nom_fichier, organisateurs, uids):
    """ Met à jour le fichier CSV UID,EMAIL à partir du dictionnaire """
    nouveaux_uids = False
    for id_reunion in organisateurs:
        if organisateurs[id_reunion]["id_organisateur"] not in uids:
            uids[organisateurs[id_reunion]["id_organisateur"]] = organisateurs[id_reunion]["email_organisateur"]
            nouveaux_uids = True

    if nouveaux_uids:
        with open(nom_fichier, "w", encoding="utf-8") as fichier:
            for uid in uids:
                fichier.write(f"{uid},{uids[uid]}\n")

    return uids

################################################################################
def lister_organisateurs(reunions):
    """ Lister les réunions au format CSV """
    print("#meeting_id,organizer_email,organizer_id,organizer_organization,meeting_type,first_join,last_leave,number_attendees")
    for k, v in reunions.items():
        print(f'{k},{v["email_organisateur"]},{v["id_organisateur"]},{v["id_organisation"]},{v["type_reunion"]},{v["premier_arrive"]},{v["dernier_parti"]},{len(v["participants"])}')

################################################################################
def lister_participants(reunions, uids):
    """ Lister les connexions des participants de réunions au format CSV """
    print("#meeting_id,attendee_key,attendee_email,key_type,attendee_organization,join_time,leave_time,client_ip,device,property")
    for kr in reunions: # kr = clé de réunion
        for kp in reunions[kr]: # kp = clé de participant
            participant = ""
            if kp in uids:
                participant = uids[kp]
            for c in reunions[kr][kp]: # c = connexion
                print(f'{kr},{kp},{participant},{c["type_cle"]},{c["id_organisation"]},{c["debut"]},{c["fin"]},{c["adresse_ip"]},{c["materiel"]},{c["propriete"]}')

################################################################################
def lister_deconnexions(organisateurs, participants, uids, filtre):
    """ Liste les réunions/participants/connexions avec suspicion de déconnexion """
    reunions_affectees = 0
    participants_affectes = 0
    total_participants = 0
    for id_reunion in participants:
        infos_reunion = False
        reunion_affectee = False
        total_participants += len(participants[id_reunion])
        for cle_participant in participants[id_reunion]:
            infos_participant = False

            devices = {}
            for connexion in participants[id_reunion][cle_participant]:
                if not filtre or filtre.search(connexion["adresse_ip"]):
                    device = connexion["materiel"]
                    if not device:
                        device = "?"
                    debut_connexion = re.sub(r".*T", "", connexion["debut"])
                    fin_connexion = re.sub(r".*T", "", connexion["fin"])
                    if device in devices:
                        devices[device].append(f'    Time: {debut_connexion} - {fin_connexion} / IP address: {connexion["adresse_ip"]:15s} / Device: {connexion["materiel"]} / Property: {connexion["propriete"]}')
                    else:
                        devices[device] = [f'    Time: {debut_connexion} - {fin_connexion} / IP address: {connexion["adresse_ip"]:15s} / Device: {connexion["materiel"]} / Property: {connexion["propriete"]}']

            participant_affecte = False
            for device, connexions in devices.items():
                if len(connexions) > 1:
                    participant_affecte = True
                    reunion_affectee = True
                    if not infos_reunion:
                        # Informations sur la réunion :
                        date_reunion = re.sub(r"T.*", "", organisateurs[id_reunion]["premier_arrive"])
                        debut_reunion = re.sub(r".*T", "", organisateurs[id_reunion]["premier_arrive"])
                        fin_reunion = re.sub(r".*T", "", organisateurs[id_reunion]["dernier_parti"])
                        print(f'Meeting ID: {id_reunion} / Type: {organisateurs[id_reunion]["type_reunion"]} / Date: {date_reunion} / Time: {debut_reunion} - {fin_reunion} / #Attendees: {len(organisateurs[id_reunion]["participants"])}')
                        infos_reunion = True

                    if not infos_participant:
                        # Informations sur le participant :
                        if cle_participant in uids:
                            print(f'  Attendee: {cle_participant} / Key type: {participants[id_reunion][cle_participant][0]["type_cle"]} / Email: {uids[cle_participant]} / Organization ID: {participants[id_reunion][cle_participant][0]["id_organisation"]}')
                        else:
                            print(f'  Attendee: {cle_participant} / Key type: {participants[id_reunion][cle_participant][0]["type_cle"]} / Organization ID: {participants[id_reunion][cle_participant][0]["id_organisation"]}')
                        infos_participant = True

                    # reconnexions suspectes :
                    for connexion in connexions:
                        print(connexion)
                    print()
            if participant_affecte:
                participants_affectes += 1
        if reunion_affectee:
            reunions_affectees += 1

    print("=====")
    print(f"{reunions_affectees} meetings affected out of {len(participants)} ({100 * reunions_affectees / len(participants):.1f}%)")
    print(f"{participants_affectes} attendees affected out of {total_participants} ({100 * participants_affectes / total_participants:.1f}%)")

################################################################################
def traiter_fichier(fichier, uids):
    """ Traite une source et retourne les uids mis à jour """
    organisateurs, participants = extraire_reunions(fichier, parametres["Afficher contenu"])

    if parametres["Base utilisateurs"]:
        uids = mettre_a_jour_uids(parametres["Base utilisateurs"], organisateurs, uids)

    if parametres["Lister organisateurs"]:
        lister_organisateurs(organisateurs)
    elif parametres["Lister participants"]:
        lister_participants(participants, uids)
    elif parametres["Lister deconnexions"]:
        lister_deconnexions(organisateurs, participants, uids, parametres["Filtre adresses"])

    return uids

################################################################################
def main():
    """ Point d'entrée du programme """
    nom_programme = os.path.basename(sys.argv[0])

    _initialisation_journalisation(nom_programme)
    _gestion_signaux()
    arguments = _gestion_ligne_commande()

    exit_status = 0

    uids = {}
    if parametres["Base utilisateurs"]:
        uids = charger_uids(parametres["Base utilisateurs"])

    if arguments:
        for argument in arguments:
            if os.path.isfile(argument):
                # Traitement du fichier :
                with open(argument, "r", encoding="utf-8") as fichier:
                    uids = traiter_fichier(fichier, uids)

            else:
                logging.error(f"'{argument}' is not a file name")
                exit_status += 1
    else:
        # Traitement des données sur l'entrée standard :
        fichier = sys.stdin
        uids = traiter_fichier(fichier, uids)

    sys.exit(exit_status)


if __name__ == "__main__":
    main()
