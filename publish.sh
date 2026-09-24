#!/bin/bash
# Copy the latest deck into deck/ and push. Render redeploys automatically.
cd "$(dirname "$0")"
cp ~/Bismarck-RFP-Deck/Bismarck-Presentation.html deck/ && rsync -a --delete ~/Bismarck-RFP-Deck/img/ deck/img/
git add -A && git commit -qm "Update deck" && git push -q && echo "Pushed. Render redeploys in about a minute."
