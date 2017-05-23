#! /usr/bin/env node

var jsf = require('json-schema-faker');
var util = require('util');
var schema = require('./schema.json');


jsf.resolve(schema).then(function(obj) {
    console.log(JSON.stringify(obj, null, 4));
});
