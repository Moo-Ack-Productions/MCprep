def prep_simple(bpy_ctx, mcprep_diffuse):
    pass

def register():
    return {
        "engine" : "CYCLES",
        "mat_type" : "simple",
        "prep_func" : prep_simple
    }
