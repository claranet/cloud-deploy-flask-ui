# Claranet Cloud Deploy UI

## Updating AWS data
Requires curl, nodejs and jq:

    (echo 'function callback(data) { console.log(JSON.stringify(data)); }'; curl -s 'http://a0.awsstatic.com/pricing/1/ec2/linux-od.min.js') | nodejs | jq -r '.config.regions' > data/aws_data_instance_types.json
    (echo 'function callback(data) { console.log(JSON.stringify(data)); }'; curl -s 'https://a0.awsstatic.com/pricing/1/ec2/previous-generation/linux-od.min.js') | nodejs | jq -r '.config.regions' > data/aws_data_instance_types_previous.json
