"""Native Gym supervisor entrypoint; install mathematics-rl[nemo] in its server environment."""

from mathematics_rl.adapters.nemo import MathematicsResourcesServer

if __name__ == "__main__":
    MathematicsResourcesServer.run_webserver()
