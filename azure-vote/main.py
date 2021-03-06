from flask import Flask, request, render_template
import os
import random
import redis
import socket
import sys
import logging
from datetime import datetime

# App Insights
# TODO: Import required libraries for App Insights
from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure import metrics_exporter
from opencensus.stats import aggregation as aggregation_module
from opencensus.stats import measure as measure_module
from opencensus.stats import stats as stats_module
from opencensus.stats import view as view_module
from opencensus.tags import tag_map as tag_map_module
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace.samplers import ProbabilitySampler
from opencensus.trace.tracer import Tracer
from opencensus.ext.flask.flask_middleware import FlaskMiddleware

from applicationinsights.flask.ext import AppInsights
from applicationinsights import TelemetryClient


app = Flask(__name__)

# Load configurations from environment or config file
app.config.from_pyfile('config_file.cfg')

print("Instrument id is: {0}".format(app.config['INSTRUMENTATION_KEY_FULL']))
# Logging
logger = logging.getLogger(__name__)
logger.addHandler(AzureLogHandler(
    connection_string=app.config['INSTRUMENTATION_KEY_FULL'])
)

# Metrics
exporter = metrics_exporter.new_metrics_exporter(
               enable_standard_metrics=True,
               connection_string=app.config['INSTRUMENTATION_KEY_FULL'])

# Tracing
tracer = Tracer(
    exporter=AzureExporter(
        connection_string=app.config['INSTRUMENTATION_KEY_FULL']),
    sampler=ProbabilitySampler(1.0),
)



# Requests
middleware = FlaskMiddleware(
    app,
    exporter=AzureExporter(connection_string=app.config['INSTRUMENTATION_KEY_FULL']),
    sampler=ProbabilitySampler(rate=1.0),
)


if ("VOTE1VALUE" in os.environ and os.environ['VOTE1VALUE']):
    button1 = os.environ['VOTE1VALUE']
else:
    button1 = app.config['VOTE1VALUE']

if ("VOTE2VALUE" in os.environ and os.environ['VOTE2VALUE']):
    button2 = os.environ['VOTE2VALUE']
else:
    button2 = app.config['VOTE2VALUE']

if ("TITLE" in os.environ and os.environ['TITLE']):
    title = os.environ['TITLE']
else:
    title = app.config['TITLE']

# Redis Connection
r = redis.Redis()

# Change title to host name to demo NLB
if app.config['SHOWHOST'] == "true":
    title = socket.gethostname()

# Init Redis
if not r.get(button1): r.set(button1,0)
if not r.get(button2): r.set(button2,0)

# Custom events
#app.config['APPINSIGHTS_INSTRUMENTATIONKEY'] = 'InstrumentationKey=9db51273-db0c-4c77-be9e-bcfef72dfdfa'
# log requests, traces and exceptions to the Application Insights service
appinsights = AppInsights(app)


@app.route('/', methods=['GET', 'POST'])
def index():

    if request.method == 'GET':

        # Get current values
        vote1 = r.get(button1).decode('utf-8')
        # TODO: use tracer object to trace cat vote
        tracer.span(name=button1)
        vote2 = r.get(button2).decode('utf-8')
        # TODO: use tracer object to trace dog vote
        tracer.span(name=button2)

        # Return index with values
        return render_template("index.html", value1=int(vote1), value2=int(vote2), button1=button1, button2=button2, title=title)

    elif request.method == 'POST':

        if request.form['vote'] == 'reset':

            vote1 = r.get(button1).decode('utf-8')
            vote2 = r.get(button2).decode('utf-8')
            # Empty table and return results
            r.set(button1,0)

            r.set(button2,0)

            try:
                if int(vote1) > 0:
                    properties = {'custom_dimensions': {'Cats Vote': vote1}}
                    # TODO: use logger object to log cat vote
                    with tracer.span(name=vote1) as span:
                        logger.warning('cat vote', extra=properties)

                if int(vote2) > 0:
                    properties = {'custom_dimensions': {'Dogs Vote': vote2}}
                    # TODO: use logger object to log dog vote
                    with tracer.span(name=vote2) as span:
                        logger.warning('dog vote', extra=properties)
            except ValueError as e:
                logger.error("Error - not integers {0}".format(e))

            return render_template("index.html", value1=int(vote1), value2=int(vote2), button1=button1, button2=button2, title=title)

        else:

            # Insert vote result into DB
            vote = request.form['vote']
            with tracer.span(name=vote) as span:
                r.incr(vote, 1)

            # Get current values
            vote1 = r.get(button1).decode('utf-8')
            vote2 = r.get(button2).decode('utf-8')

            tc = TelemetryClient(app.config['INSTRUMENTATION_KEY'])
            if vote == button1: #button1 = Cats
                tc.track_event('Cats vote')
            else: 
                tc.track_event('Dogs vote')

            tc.flush()

            # Return results
            return render_template("index.html", value1=int(vote1), value2=int(vote2), button1=button1, button2=button2, title=title)

if __name__ == "__main__":
    # comment line below when deploying to VMSS
    #app.run() # local
    # uncomment the line below before deployment to VMSS
    app.run(host='0.0.0.0', threaded=True, debug=True) # remote
