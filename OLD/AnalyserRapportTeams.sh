#!/bin/sh

if [ "$#" != "1" ]
then
    echo "Erreur : Indiquez le nom du fichier CSV à traiter en argument de la ligne de commande"
    exit 1
fi

if [ ! -f "$1" ]
then
    echo "Erreur : Le fichier indiqué n'existe pas !"
    exit 1
fi

if [ ! -f utilisateurs.csv ]
then
    touch utilisateurs.csv
fi

################################################################################

preparation()
{
    tail +2 $1 \
    | sort \
    | uniq \
    > $1.sans_doublons.txt
    
    ReformaterRapportTeams.py --voir $1.sans_doublons.txt \
    > $1.txt
    
    ReformaterRapportTeams.py --lister $1.sans_doublons.txt \
    | sort \
    | uniq \
    > $1.participants.txt
}

analyse_utilisateurs()
{
    # crée ou met à jour une base de données "UUID,EMAIL" nommée utilisateurs.csv

    egrep "User(Key|Id)=" $1.txt \
    | sed "s/.*=//" \
    | paste - - \
    | sort \
    | uniq \
    | sed "s/	/,/" \
    | while read LIGNE
    do
        UUID=`echo ${LIGNE} | cut -d"," -f1`
        MEL=`echo ${LIGNE} | cut -d"," -f2`

        EXISTE=`grep "^${UUID}," utilisateurs.csv`
        if [ "${EXISTE}" = "" ]
        then
            echo "${UUID},${MEL}" >> utilisateurs.csv
        else
            MEL_EXISTANT=`echo ${EXISTE} | cut -d"," -f2`
            if [ "${MEL}" != "${MEL_EXISTANT}" ]
            then
                echo "${UUID}: ${MEL_EXISTANT} -> ${MEL}"
            fi
        fi
    done
}

analyse_reunions()
{
    # On cherche tous les participants qui se sont connectés plus d'une fois à une réunion
    # Puis on boucle sur ces réunions
    cut -d"," -f1,2 $1.participants.txt \
    | sort \
    | uniq -c \
    | grep -v "   1 " \
    | sed "s/^ *[0-9]* //" \
    | cut -d"," -f1 \
    | uniq \
    | while read MID
    do
        DATE=`grep "\"\"MeetingDetailId\"\":\"\"${MID}\"\"" $1.sans_doublons.txt | head -1 | sed -e 's/.*""JoinTime"":""//' -e 's/T.*//'`
        echo "Réunion ${MID} du ${DATE}:"

        grep "^${MID}," $1.participants.txt \
        | cut -d"," -f2 \
        | sort \
        | uniq -c \
        | grep -v "   1 " \
        | sed "s/^ *[0-9]* //" \
        | while read UOI
        do
            MEL=`grep "^${UOI}," utilisateurs.csv | cut -d"," -f2`
            grep "^${MID},${UOI}," $1.participants.txt \
            | sed "s/${MID}/${MEL}/" \
            | sed "s/20[0-9][0-9]-[0-1][0-9]-[0-2][0-9]T//g" \
            | sed "s/,/	/g" \
            | sed "s/^/  /"
        done
        echo
    done \
    > $1.reunions_a_investiguer.txt
}
 
analyse_devices()
{
    grep DeviceInformation $1.txt \
    | sed "s/  DeviceInformation=//" \
    | sort \
    | uniq -c \
    | sort -rn \
    > $1.devices.txt
}

stats()
{
    echo "Source : $1"
    echo "========"

    NB_LIGNES=`cat $1 | wc -l | sed -e "s/^ *//" -e "s/ .*//"`
    echo "Lignes                           : ${NB_LIGNES}"

    NB_LIGNES=`cat $1.sans_doublons.txt | wc -l | sed -e "s/^ *//" -e "s/ .*//"`
    echo "Lignes dédoublonnées             : ${NB_LIGNES}"

    NB_REUNIONS=`grep MeetingDetailId $1.txt | sort | uniq | wc -l | sed "s/[^0-9]//g"`
    echo "Nombre de réunions               : ${NB_REUNIONS}"

    NB_REUNIONS=`grep Réunion $1.reunions_a_investiguer.txt | wc -l | sed "s/[^0-9]//g"`
    echo "Nombre de réunions à investiguer : ${NB_REUNIONS}"

    NB_PERSONNES=`grep UserObjectId $1.txt | sort | uniq | wc -l | sed "s/[^0-9]//g"`
    echo "Nombre de personnes uniques      : ${NB_PERSONNES}"
}

preparation $1
analyse_utilisateurs $1
analyse_reunions $1
stats $1 | tee $1.stats
analyse_devices $1

exit 0
