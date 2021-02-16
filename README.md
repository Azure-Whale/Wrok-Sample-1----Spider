# E-commerce Spider

This is a small code sample of my most recent work. It can become a reference for how I write my code in the working environment.

The spider will crawl items in good quality on Sephora automatically through selenium and scrapy, then deliver the data to the AWS RDS and DynamoDB after tests passed.

To see how it works in our product, you may go to our website and take a look: https://busysquirrels.com/?category=Sephora

# Workflow:
1. The spider would initially collect item records and store them in AWS RDS, tables there would store all available items of target store

2. The spider would fetch product page links from the AWS RDS I stored in step-1, and then visit these products in order to update product status as I need to track product price and availability.

3. The most recent update record of each item would be stored in DynamoDB, the website would fetch data from it through the corresponding APIs and present them on the front(like the pic below)

![alt text](https://github.com/Azure-Whale/Wrok-Sample-1----Spider/blob/main/screen_shot.jpg)
