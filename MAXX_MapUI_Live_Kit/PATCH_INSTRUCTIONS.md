# Apply Visual Update 2 to an existing installation

The screenshot showing “Saved Dijkstra route: 1.74 km” and zero buildings/deliveries is the original static map. The new page preserves that map-first appearance and supplies the new functionality. It is served by this kit's Python server.

1. Download `MAXX_MapUI_Visual_Fix.ps1` to Downloads.
2. In the terminal currently running this kit's server, press **Ctrl+C**.
3. At your PyCharm Terminal prompt, paste this ONE command and press Enter:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\Downloads\MAXX_MapUI_Visual_Fix.ps1" -Repository "C:\Users\noyes\PycharmProjects\MAXX-Map-Submission"
```

4. After the patch reports success, paste this ONE command and press Enter:

```powershell
python .\MAXX_MapUI_Live_Kit\server.py
```

5. Keep that terminal running. Open [the updated classic map](http://127.0.0.1:8000/world.html) and press Ctrl+F5.
6. Confirm [the version endpoint](http://127.0.0.1:8000/api/version) says **MapUI Visual Update 2**.

The canonical path is also available on the correct server: `http://127.0.0.1:8000/html/web/public/dave-campus-map/gis-layers.html`. Use 127.0.0.1 explicitly if localhost is still reaching another server or old IPv6 listener. Do not kill an unknown process. The patch changes no port permissions or firewall settings.

The patch checks MapUI/origin, backs up the prior kit in `LocalAppData\MAXXMapBackups`, then updates code/docs. Existing map data, public-source cache and actual field reports remain local and are preserved. It does not modify the original team map HTML, stage files, commit, push or deploy. If the prior kit contains your edits, they remain in the printed backup path.

Expected: OSM street background, 145 blue building outlines, 885 green path features, six maroon numbered targets, Southside Dining B marker, eight red access-tag restrictions with matching restricted-entry symbols, purple outbound and orange dashed return. Source counts are snapshot-specific and can change after an explicit map refresh.

Weighted heat, routing-node scores and public source connections remain part of this page. Heat does not invent current crowds outside active source windows. Use the bottom-left control to switch advanced layers.

Run `python -m unittest discover -s .\MAXX_MapUI_Live_Kit\tests -v` from repository root after patching. Review the current guide for MapUI staging/pushing; actual runtime reports must stay out of Git.
