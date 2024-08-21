Explanation of the file system layout on archer2

- work
|- e820
 |- e820
  |- willpizii
   |- run
    |- runmodels - directory containing all complete run models
     |- mod_def - single fault model
     |- mod_XXXx_YYYy_ZZz - model file directories

    |- comparison
     |- comparison_pandas.ipynb and outputs

    |- runmodels_var - smooth V_PL run models
    |- comparison_var - smooth V_PL run model comparison

   |- qdynbin - special folder to contain working qdyn binary
   |- qdyn - qdyn repository
   |- QENV - python environment folder

   |- working - working models, recent models
    |- circ_3d - models with a circular asperity
    |- en_ech_3d - misc models of normal asperity shape
    |- far_y_3d - models at high separation
    |- gap_fill_3d - models at spacings around island of chaos
    |- high_r_3d - various models at different separations, in gaps
    |- rest_3d - more gap-filling models at various separations
    |- shallow_3d - various models tested close to the surface instead of buried
    |- smooth_v_3d - models with velocity smoothed across overlap to sum to V_PL
    |- test_r_3d - comparison of CRP and my smoothed asperities at 100%O, low S
    |- vary_s_3d - various other experimental models, including down-dip


