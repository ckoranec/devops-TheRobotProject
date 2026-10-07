<?php
// Fetch server information dynamically
$public_ip = shell_exec("curl -s http://169.254.169.254/metadata/v1/interfaces/public/0/ipv4/address");

?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>MAXX Energy</title>
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
<h1> Welcome to MAXX Energy! </h1>
</body>
</html>
