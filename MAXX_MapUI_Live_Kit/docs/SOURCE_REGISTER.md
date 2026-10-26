# Verified source register - October 26, 2026

| Source | Verification and actual scope | App use |
|---|---|---|
| [MapUI](https://github.com/ckoranec/devops-TheRobotProject/tree/MapUI) | Branch exists; checked at commit e88c2cc23ef9ddc495056151b1379eb7b3b1df71 | Team baseline/provenance; no remote writes performed |
| [OSM map API](https://api.openstreetmap.org/api/0.6/map?bbox=-77.312,38.827,-77.299,38.835) | Successful XML response, normalized to 145 buildings and 885 path/restriction features in a central-campus bbox | Real geometry snapshot; not live obstacle sensing |
| [Mason Construction](https://construction.gmu.edu/) | Official page directly links the following public ArcGIS experience | Authority/discovery chain |
| [Project Map experience](https://experience.arcgis.com/experience/55b5f8173f1d4286a1bf8ba7dc43d263) | Public app data identifies Project_Polygons layer | Discovery chain to structured data |
| [Project_Polygons service](https://services1.arcgis.com/knq5Ad7sB7AS2ev7/arcgis/rest/services/Project_Polygons/FeatureServer/6) | Public read Query service; schema phase/footprint; 30 public-status polygons returned by the app query during validation, including three Construction-phase records | Actual project overlays; optional conservative avoidance, not asserted confirmed closures |
| [Communication Career Forum](https://communication.gmu.edu/events/18428) | Official event details: Johnson Center, Oct 27, 8:30 AM-12:30 PM Eastern | Published context |
| [Verified event iCalendar](https://communication.gmu.edu/events/18428.ics) | Successful VCALENDAR/VEVENT response; declared America/New_York | Actual schedule/location input; low-confidence predicted crowd effect |
| [Mason scheduling](https://brand.gmu.edu/events/internal-clients/scheduling) | Documents 25Live and published calendars | Future full approved feed path; not falsely claimed connected |

The general Today@Mason Trumba JSON/RSS probes returned errors; they are not active adapters in this kit. No private calendars, student schedules, phone GPS or physical robot telemetry were accessed. Synthetic robot JavaScript in the repository uses software grid coordinates and generated battery values, so it cannot verify a physical robot's location.

Successful fetch metadata is stored under data/public-cache. Failures appear in runtime source status; they do not create fabricated replacement observations. The build verified current public reads; your local network must still be able to reach these sources. Source counts and publisher content can change after this build.
