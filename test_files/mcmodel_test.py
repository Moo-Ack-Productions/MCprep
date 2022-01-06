"""Test MC Model spawning by iterating through whole list.

Will be slow, spawning each one, and listing which ones have errors.
"""

import bpy

MAX_CHECK = 2000


def check_models(context):
	bpy.ops.mcprep.reload_models()

	scn_props = context.scene.mcprep_props
	scn_props.model_list_index = 0

	exceptions = []
	successful = []

	count = len(scn_props.model_list)
	prior_obj = None

	print("Total to process: ", count)

	for index in range(len(scn_props.model_list)):
		# scn_props.model_list_index = index
		model = scn_props.model_list[index]

		try:
			bpy.ops.mcprep.spawn_model(filepath=model.filepath, skipUsage=True)

			new_obj = context.object
			if new_obj != prior_obj:
				prior_obj = new_obj
			else:
				exceptions.append([model.name, "object was same between iteration"])
				print("Object was the same between iterations")
				break
			if len(new_obj.data.vertices) < 4:
				exceptions.append([model.name, "Not enough geo generated"])
				print("#{} {} failed".format(
					index, model.name))
			else:
				successful.append(model.name)
		except Exception as err:
			exceptions.append([model.name, str(err)])
			print(f"{model.name} failed")
		finally:
			print("#{}/{}".format(index, count))

		bpy.ops.object.delete(use_global=True)

		if MAX_CHECK <= index:
			break

	print("Succeeded: {}, failed: {}".format(
		len(successful),
		len(exceptions)))

	if not exceptions:
		print("No failures!")
	else:
		print("Those that failed:")
		for itm in exceptions:
			print("{}: {}".format(itm[0], itm[1]))


check_models(bpy.context)
print("Finished check")
