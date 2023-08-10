# What is BDK?
The Broadband Data Kit (BDK) is a tool developed by the SPIN Lab at Virginia Tech to aid you in completing your bi-annual FCC required BDC filing by providing an intuitive and automated solution. Features we provide are: 
* `Visualization`: Get a clear overview of your network data. See which fabric locations are served by your network, ensuring you have a comprehensive understanding of your coverage.

* `Dynamic Map Editing`: We understand that networks are ever-evolving. With our dynamic map editing feature, you can update and document the fabric locations your network serves as they change over time.

* `Automated Reporting`: Once you input your data and specify the locations you cover, BDK will generate a customized report, formatted and compliant with FCC guidelines, ready for submission.

# Where to begin? 
We offer multiple ways to utilize BDK:

* `Web Service`: If you're primarily interested in the service, visit BDK Web Portal.

* `Local Deployment`: For those who prefer a local setup, there are two options:

   1) Docker: Run the docker container using the docker4main branch.
   2) Manual Setup: If you want more granular control, follow the setup instructions on the dev branch. This approach gives you control over the Flask server, Next.js front-end, and Celery/Redis asynchronous workers.

Installation instructions are located on the associated branches. 


# How does it work? 

The core workflow of BDK is outlined as follows:

1) `Upload Network Data`: Provide your network data in KML format. Use line-strings for wired connections and polygons for wireless coverage. Additionally, upload your Fabric dataset.
* This tool was developed with Fabric Version 2, and is in the process of being updated for Fabric Version 3

2) `Coverage Computation`: We analyze the provided datasets to identify which locations in the Fabric dataset are covered by your network.

* For wireless data, please note that as of August 2023, we do not employ LiDAR for coverage determination.
* For wired data, we calculate coverage by identifying all locations within a 100m radius of the fiber route, ensuring an accurate estimation.
3) `Visualization`: After processing, your data is displayed on a map. This interactive feature lets you zoom in to specific locations, enabling you to validate the tool's accuracy.

   #### The map will be color-coded in the following manner:
   
   | Color             | Hex                                                                |
   | ----------------- | ------------------------------------------------------------------ |
   | Purple | ![#800080](https://via.placeholder.com/10/800080?text=+) Your Network Coverage |
   | Green | ![#008000](https://via.placeholder.com/10/008000?text=+) Served Fabric Locations (BSL)|
   | Red | ![#FF0000](https://via.placeholder.com/10/FF0000?text=+) Unserved Fabric Locations (BSL)|
   | Orange| ![#FFA500](https://via.placeholder.com/10/FFA500?text=+) Non-BSL Locations |


4) `Editing`: If discrepancies arise or adjustments are required, use the integrated editing tool to make necessary changes.

5) `Report Generation`: Once you're satisfied with the accuracy and coverage details, simply click the 'Export' button on the navbar to download your comprehensive report.
# Demo

A video demonstration of how to use this tool will be provided at a later date 
# Tech Stack

| Category                   | Technology/Libraries                                 |
|----------------------------|------------------------------------------------------|
| Client                 | 🌐 [Next.js](https://nextjs.org/)                |
| Server                 | 🚀 [Flask](https://flask.palletsprojects.com/)   |
| Database               | 📦 [PostgreSQL](https://www.postgresql.org/)     |
| Asynchronous Processing| 🔄 Redis & [Celery](https://docs.celeryproject.org/en/stable/) |
| Production Tools       | 🐳 [Docker](https://www.docker.com/) & 🌐 [Nginx](https://www.nginx.com/) &  🦄 [Gunicorn](https://gunicorn.org/) |
| Third-Party Libraries  | 🗺️ [Maplibre GL JS](https://github.com/maplibre/maplibre-gl-js) & [Tippecanoe](https://github.com/mapbox/tippecanoe) |

# Contributing

Contributions are always welcome!

To get started, please refer to our `contributing.md`.

It's crucial to adhere to this project's `code of conduct` to maintain a positive and inclusive environment. We maintain a list of potential optimizations and tasks in the `Github Issues` section. Feel free to pick one from there, or suggest your own improvements!

# Authors

- **Professor Shaddi Hasan** 
  - Duration: Summer 2023 - Present
  - GitHub: [@shaddi](https://github.com/shaddi)

- **Vineet Marri** 
  - Duration: Summer 2023 - Present
  - GitHub: [@vineetm3](https://github.com/vineetm3)

- **Zhuowei Wen** 
  - Duration: Summer 2023 - Present
  - GitHub: [@ZhuoweiWen](https://github.com/ZhuoweiWen)
