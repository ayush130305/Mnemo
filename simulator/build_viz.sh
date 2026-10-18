#!/bin/sh
# Builds the single-file visual simulator: python3 mnemo_sim.py first, then this script
cd "$(dirname "$0")"
python3 -c "
t = open('viz/template.html').read()
d = open('viz/data.json').read()
open('viz/mnemo_sim_visual.html', 'w').write(t.replace('__DATA__', d))
"
echo "wrote viz/mnemo_sim_visual.html"
