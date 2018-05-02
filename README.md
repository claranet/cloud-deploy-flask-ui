# Claranet Cloud Deploy UI

## Configuration
* copy config.yml.sample as config.yml
* customize your UI as you want using the config.yml parameters

## Updating AWS data
Requires curl, nodejs and jq:

    (echo 'function callback(data) { console.log(JSON.stringify(data)); }'; curl -s 'http://a0.awsstatic.com/pricing/1/ec2/linux-od.min.js') | nodejs | jq -r '.config.regions' > data/aws_data_instance_types.json
    (echo 'function callback(data) { console.log(JSON.stringify(data)); }'; curl -s 'https://a0.awsstatic.com/pricing/1/ec2/previous-generation/linux-od.min.js') | nodejs | jq -r '.config.regions' > data/aws_data_instance_types_previous.json
    curl -s 'http://docs.amazonaws.cn/en_us/general/latest/gr/rande.html' | node -e 'r=[];x=require("fs").readFileSync(0,"utf-8").split("(Amazon EC2)</h2>")[1].split("</table>")[0].split("<tr>").slice(2).forEach(function(l){s=l.split("</td>");r.push({Region:s[1].split("<td>")[1],Location:s[0].split("<td>")[1]});});r.sort(function(a,b){if(a.Region<b.Region)return -1;if(a.Region>b.Region)return 1;return 0;});console.log(JSON.stringify(r, null, 2));' > data/aws_data_regions_locations.json
