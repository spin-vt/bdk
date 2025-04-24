---
title: FAQ
parent: Developer Documentation
nav_order: 3
---

# FAQ

1. Cannot bind to port number due to permission denied
> This is usually because the port number you are trying to run the backend or frontend on is already occupied. Change the port number (the last four digits in > the URL) at **NEXT_PUBLIC_DEVELOP_BACKEND_URL** in the **.env.local file** and at **DEVELOP_BACKEND_PORT** in the **.env** file. Make sure they match.