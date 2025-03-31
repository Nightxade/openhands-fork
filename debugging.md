# Remove workspace folder
`docker run -v /srv/home/matthewcai/OpenHands:/home/pn -it openhands-env /bin/bash`

# Run openhands
`poetry run python -m openhands.core.cli -f prompt.txt | tee traces/SAVE_TRACE`
