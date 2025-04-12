# tala - (Microsoft) Teams Audit Log Analyzer

## What is it?
A portable Python-only tool to process Microsoft Teams Audit Logs.

The original goal was to help spot network issues (connections lost) by looking at people making multiple successive connections to the same meeting with the same device.

[![Servier Inspired](https://raw.githubusercontent.com/servierhub/.github/main/badges/inspired.svg)](https://github.com/ServierHub/)

## Usage
```
usage: tala [--debug] [--help|-?] [--version]
       [-o|--organizers] [-a|--attendees]
       [-u|--users FILE]
       [-d|--disconnect] [-i|--ip REGEX]
       [--] [file ...]
  ---------------  -------------------------------------------------
  -o|--organizers  List meetings organizers
  -a|--attendees   List meetings attendees
  -d|--disconnect  List meetings disconnections
  -i|--ip REGEX    Filter meeting disconnections by IP address regex
  -u|--users FILE  create/update and use the FILE users database
  --debug          Enable debug mode
  --help|-?        Print usage and this help message and exit
  --version        Print version and exit
  --               Options processing terminator
```
You can use the command either as a filter (cat my_log_file | tala) or as a file processor (tala my_log_file).

You can either use it:
* to display an audit log in human readable format (no args)
* to produce a CSV file with the relevant meetings/organizers information (-o)
* to produce a CSV file with the relevant meetings/attendees information (-a)
* to produce/update/use a CSV file with UUID,EMAIL of organizers/attendees (-u FILE)
* to analyze suspected disconnection cases (-d)
  * you can restrict cases to the ones made from specific IP addresses (-i REGEX), as you normally don't care about people connecting from home rather than your internal enterprise network.
    * for example "^10\\.5[78]\\." for IPv4 addresses beginning with "10.57." or "10.58.".
  * you can use the CSV file with UUID,EMAIL to identify attendees encountering network issues (-u FILE)

Please note that the suspected disconnection cases are still crude so far, and contain false positives (for example, when you have multiple rather than successive connections to the same meeting, using different devices).

## Audit log file format

| Line | Content | Usual values |
| --- | --- | --- |
| 1 | header line | "CreationDate,UserId,Operation,AuditData" |
| 2-50001 | content lines | field1,field2,field3,field4 |

The audit data used to be truncated at 50.000 lines per extract file. If you have files with exactly 50.001 lines, try exporting data on a shorter time span.

NB: The fields can be in any order and there may be additional fields but *tala* expects at least the 4 mentioned above, with a comma-separator.

### Content lines format

| Field | Usual values |
| --- | --- |
| CreationDate | a date in "YYYY-MM-JJThh:mm:ss.0000000Z" format |
| UserId | the email address of the organizer (that field was formerly called "UsedIds") |
| Operation | apparently always "MeetingParticipantDetail", but according to the references below there are other possible values (that field was formerly called "Operations") |
| AuditData | see below... |

#### AuditData field format

| Field | Usual values |
| --- | --- |
| CreationTime | a date in "YYYY-MM-JJThh:mm:ss" format |
| Id | the record [UUID](https://en.wikipedia.org/wiki/Universally_unique_identifier) |
| Operation | apparently always "MeetingParticipantDetail" |
| OrganizationId | the organizer's organisation UUID ([Microsoft 365 tenant ID](https://www.whatismytenantid.com/)) |
| RecordType | apparently always 25 |
| UserKey | the organizer UUID |
| UserType | apparently always 0 |
| Version | apparently always 1 |
| Workload | apparently always "MicrosoftTeams" |
| ClientIP | an IPv4 or IPv6 address (usually the one before a proxy) |
| UserId | the email address of the organizer |
| ArtifactsShared | a list. Not always present. See below |
| Attendees | a list of 1 element. See below |
| DeviceId | some code (maybe for devices enrolled in Intune?). Not always present |
| ExtraProperties | a list. See below |
| JoinTime | the meeting join date in "YYYY-MM-JJThh:mm:ss" format |
| LeaveTime | the meeting leave date in "YYYY-MM-JJThh:mm:ss" format |
| MeetingDetailId | the meeting UUID |
| DeviceInformation | a string describing the device used by the attendee |
| ItemName | a value with a comma-separated combination of the following words: "ScheduledMeeting", "RecurringMeeting", "AdHocMeeting", "Escalation", "Transfer", "CallQueue", "AutoAttendant", "MicrosoftTeams", "ChannelMeeting", "ScreenSharingCall", "Broadcast", "Streaming", "Cast", "Complete", "31" |

#### ArtifactsShared sub-field format

| Sub-field | Usual values |
| --- | --- |
| ArtifactSharedName | apparently always "videoTransmitted" or ""screenShared" |

#### Attendees sub-field format

Can be either:

| Sub-field | Usual values |
| --- | --- |
| OrganizationId | not always present |
| RecipientType | either "InternalFederated" or "GuestFederated". Used to be either "User", "Anonymous", "Applications" or "Phone" |
| UserObjectId | the attendee's UUID when it's a "User". Not present otherwise |
| DisplayName | the display name when it's a "InternalFederated" or "GuestFederated" user, a phone number when it's a "Phone", an application UUID when it's an "Applications", "teamsvisitor:" followed by a code when it's a "Anonymous" |
| Role | apparently always 1 or 3 |
| UPN | the email address when it's an "InternalFederated" or "GuestFederated" user |

or:

| Sub-field | Usual values |
| --- | --- |
| DisplayName | an unstructured display name |
| Role | apparently always 1 or 3 |
| UPN | then email address when it's an "InternalFederated" or "GuestFederated" user |

In addition, when the meeting participant is added during the meeting, there's an "InviterInfo" record associated with one of the 2 previous types:

| Sub-field | Sub-sub-field | Usual values |
| --- | --- | --- |
| InviterInfo | InviteTime | a date in "YYYY-MM-JJThh:mm:ss" format |
| InviterInfo | OrganizationId | the inviter's organization UUID |
| InviterInfo | UserType | either "Teams", "PSTN" or "TeamsForLife" |
| InviterInfo | DisplayName | the display name of the inviter |
| InviterInfo | UPN | the email address of the inviter |
| InviterInfo | UserIdentifier | the inviter's UUID |

#### ExtraProperties sub-field format

| Sub-field | Usual values |
| --- | --- |
| Key | apparently always "UserAgent" |
| Value | something beginning with "CallSignalingAgent" (the most common one), "SkypeSpaces", "Conferencing Virtual Assistant", "Together Mode", "SkypeBot Transcription Bot Teams", "Teams Echo", "Large Gallery", "Announcement Playback Service", "SkypeBot Call Recorder Teams", "CaaEnterpriseBot", "Large gallery", "SkypeBot Teams Live Events Bot", "MicrosoftTeamsVoicemailService", "SkypeBot Teams Lightweight meeting Bot" |

## References
* [Search the audit log for events in Microsoft Teams](https://docs.microsoft.com/en-us/microsoftteams/audit-log-events#teams-activities)
* [Search the audit log in the compliance center](https://docs.microsoft.com/en-us/microsoft-365/compliance/search-the-audit-log-in-security-and-compliance?view=o365-worldwide#microsoft-teams-activities)
* [New High-Value Audit Records Capture Details of Microsoft Teams Meetings](https://office365itpros.com/2021/12/09/audit-events-teams-meetings/)

Other interesting links:
* [Microsoft Teams meeting attendance report](https://docs.microsoft.com/en-us/microsoftteams/teams-analytics-and-reports/meeting-attendance-report)
* [Microsoft Teams analytics and reporting](https://docs.microsoft.com/en-us/microsoftteams/teams-analytics-and-reports/teams-reporting-reference)
* [Use log files to monitor and troubleshoot Microsoft Teams](https://docs.microsoft.com/en-us/microsoftteams/log-files)
* [Teams troubleshooting](https://docs.microsoft.com/en-us/MicrosoftTeams/troubleshoot/teams-welcome)
