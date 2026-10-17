"use strict";

// MAX BYTE ROBOT PROJECT
// File: js
// Purpose: Generate consistent navigation links across
// the customer-facing Campus Eats website.
//
// How it works:
// 1. Define the website's navigation links.
// 2. Find the navigation container in the HTML.
// 3. Create a clickable link for each page.
// 4. Identify the currently active page.
//
// Important:
// This script creates navigation links only.
// It does not implement login, ordering, or tracking.

// Define the pages that appear in the navigation bar.
const sitePages = [
    ["Home", "index.html"],
    ["Menu", "menu.html"],
    ["Order", "order.html"],
    ["Track Delivery", "tracking.html"],
    ["Contact", "contact.html"],
    ["Login / Create Account", "login.html"]
];

// Locate the navigation container in the HTML document.
const navigation = document.getElementById("site-navigation");

// Only generate links if the container exists.
if (navigation) {

    // Determine which HTML page the visitor is viewing.
    const currentPage =
        window.location.pathname.split("/").pop() || "index.html";

    // Create a navigation link for each configured page.
    for (const [label, file] of sitePages) {

        // Create a new HTML anchor element.
        const link = document.createElement("a");

        // Set the destination and visible link text.
        link.href = file;
        link.textContent = label;

        // Mark the current page for accessibility.
        if (currentPage === file) {
            link.setAttribute("aria-current", "page");
        }

        // Insert the completed link into the navigation bar.
        navigation.appendChild(link);
    }
}
