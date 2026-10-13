<?php
// Fetch server information dynamically
$public_ip = shell_exec("curl -s http://169.254.169.254/metadata/v1/interfaces/public/0/ipv4/address");

?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Server Access Information (CE)</title>
    <style>
        table {
            width: 100%;
            border-collapse: collapse;
        }
        table, th, td {
            border: 1px solid black;
        }
        th, td {
            padding: 10px;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
        }
    </style>
</head>
<body>
    <h1>Server Access Information (CE)</h1>
    <table>
        <tr>
            <th>Name</th>
            <th>Description</th>
            <th>Endpoint / IP and port</th>
            <th>Access method</th>
            <th>User name</th>
        </tr>
        <tr>
            <td>maxx-energy</td>
            <td>Ubuntu server. Provides access to web and logging resources and a gateway to the employee database.</td>
            <td>
                138.197.107.244:22<br>
                Public_IP: <?= htmlspecialchars($public_ip) ?><br>
            </td>
            <td>ssh</td>
            <td>energy-support</td>
        </tr>
        <tr>
            <td>maxxenergy</td>
            <td>MySQL database. Holds the employee database.</td>
            <td>localhost on maxx-energy, port 3306</td>
            <td>mysql command line or client</td>
            <td>energy-support</td>
        </tr>
        <tr>
            <td>root</td>
            <td>Ubuntu server. Provides root access to web and logging resources and a gateway to the employee database.</td>
            <td>
                138.197.107.244:22<br>
                Public_IP: <?= htmlspecialchars($public_ip) ?><br>
            </td>
            <td>ssh</td>
            <td>root</td>
        </tr>        
    </table>
</body>
</html>
