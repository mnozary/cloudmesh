import cloudmesh
from pprint import pprint

cloudmesh.logger(False)
username = cloudmesh.load().username()

cloudmesh.banner("INIT MONGO")
mesh = cloudmesh.mesh("mongo")

cloudmesh.banner("ACTIVATE")
mesh.activate(username)

cloudmesh.banner("GET FLAVOR")
data = mesh.flavors(cm_user_id=username, clouds=["india"])

pprint (data)

cloudmesh.banner("GET FLAVOR")
mesh.refresh(username,types=['flavors'],names=["india"])

#
# PROPOSAL FOR NEW MESH API
#

cloudmesh.banner("LAUNCH VM INSTANCE")
result = mesh.vm_quick_launch(cloud, username)

cloudmesh.banner("TERMINATE VM INSTANCE")
server = result['server']['id']
mesh.vm_quick_delete(cloud, server, username)

