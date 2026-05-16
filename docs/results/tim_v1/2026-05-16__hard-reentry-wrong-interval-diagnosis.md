# TIM Wrong-Interval Diagnosis

- Source: `reports/tim_v0/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1/target_memory_status.csv`

## wrong_interval_1

- interval: 69.320-101.200 s
- rows: 251

### State counts

```text
state
LOCKED        247
REACQUIRED      2
UNCERTAIN       2
```

### TIM output target IDs

```text
target_track_id
1.0      250
142.0      1
```

### Best candidate IDs

```text
best_track_id
1.0      248
138.0      2
142.0      1
```

### Appearance used

```text
best_appearance_used
False    248
True       3
```

### Score statistics

| field | mean | p50 | p95 | min | max |
|---|---:|---:|---:|---:|---:|
| best_total | 0.915 | 0.931 | 0.968 | 0.243 | 1.000 |
| best_iou | 0.829 | 0.863 | 0.955 | 0.000 | 0.990 |
| best_distance | 0.998 | 1.000 | 1.000 | 0.726 | 1.000 |
| best_scale | 0.971 | 0.992 | 1.000 | 0.000 | 1.000 |
| best_confidence | 0.850 | 0.864 | 0.900 | 0.391 | 0.912 |
| best_appearance | 0.011 | 0.000 | 0.000 | 0.000 | 0.937 |
| lat_ms | 0.619 | 0.596 | 0.974 | 0.115 | 3.258 |

### First 20 rows

```text
        t      state  target_track_id  best_track_id  best_total  best_iou  best_distance  best_scale  best_confidence  best_appearance  best_appearance_used               reason
69.323041 REACQUIRED              1.0            1.0    0.978007  0.714543       0.999611    0.978066         0.771492         0.925853                  True reacquired_candidate
69.401616     LOCKED              1.0            1.0    1.000000  0.888922       0.999935    1.000000         0.786328         0.937315                  True   accepted_candidate
69.550131     LOCKED              1.0            1.0    0.947182  0.921846       0.999832    0.999113         0.813983         0.000000                 False   accepted_candidate
69.662033     LOCKED              1.0            1.0    0.940111  0.903888       0.999924    0.992048         0.816001         0.000000                 False   accepted_candidate
69.796014     LOCKED              1.0            1.0    0.917472  0.834886       0.999834    1.000000         0.811817         0.000000                 False   accepted_candidate
69.918188     LOCKED              1.0            1.0    0.882811  0.750437       0.998500    0.996458         0.776358         0.000000                 False   accepted_candidate
70.050840     LOCKED              1.0            1.0    0.871065  0.731134       0.999617    0.957461         0.787396         0.000000                 False   accepted_candidate
70.125754     LOCKED              1.0            1.0    0.893486  0.793206       0.998982    0.915107         0.852439         0.000000                 False   accepted_candidate
70.248122     LOCKED              1.0            1.0    0.911726  0.811804       0.999826    0.985906         0.844962         0.000000                 False   accepted_candidate
70.324947     LOCKED              1.0            1.0    0.955444  0.935925       0.999946    0.999113         0.838597         0.000000                 False   accepted_candidate
70.404991     LOCKED              1.0            1.0    0.936108  0.896927       0.999933    0.999113         0.795215         0.000000                 False   accepted_candidate
70.519432     LOCKED              1.0            1.0    0.925211  0.827529       0.999787    0.996458         0.889604         0.000000                 False   accepted_candidate
70.596074     LOCKED              1.0            1.0    0.960096  0.933325       0.999971    0.996458         0.881504         0.000000                 False   accepted_candidate
70.729443     LOCKED              1.0            1.0    0.906460  0.778373       0.999539    0.985906         0.889070         0.000000                 False   accepted_candidate
70.790275     LOCKED              1.0            1.0    0.930472  0.850582       0.999841    0.999113         0.867676         0.000000                 False   accepted_candidate
70.846107     LOCKED              1.0            1.0    0.929340  0.877605       0.999929    0.978065         0.820867         0.000000                 False   accepted_candidate
70.935848     LOCKED              1.0            1.0    0.637827  0.442106       0.996401    0.358603         0.599271         0.000000                 False   accepted_candidate
70.994249     LOCKED              1.0            1.0    0.849085  0.733857       0.999158    0.860771         0.748955         0.000000                 False   accepted_candidate
71.055521     LOCKED              1.0            1.0    0.932551  0.872410       0.999832    0.985906         0.846519         0.000000                 False   accepted_candidate
71.126937     LOCKED              1.0            1.0    0.943425  0.911495       0.999977    0.985906         0.828998         0.000000                 False   accepted_candidate
```

## wrong_interval_2

- interval: 110.840-116.310 s
- rows: 31

### State counts

```text
state
LOCKED        29
REACQUIRED     2
```

### TIM output target IDs

```text
target_track_id
1.0      30
161.0     1
```

### Best candidate IDs

```text
best_track_id
1.0      30
161.0     1
```

### Appearance used

```text
best_appearance_used
False    30
True      1
```

### Score statistics

| field | mean | p50 | p95 | min | max |
|---|---:|---:|---:|---:|---:|
| best_total | 0.888 | 0.900 | 0.958 | 0.609 | 0.974 |
| best_iou | 0.757 | 0.767 | 0.915 | 0.163 | 0.961 |
| best_distance | 0.999 | 1.000 | 1.000 | 0.992 | 1.000 |
| best_scale | 0.967 | 0.992 | 1.000 | 0.574 | 1.000 |
| best_confidence | 0.849 | 0.847 | 0.916 | 0.765 | 0.927 |
| best_appearance | 0.027 | 0.000 | 0.000 | 0.000 | 0.829 |
| lat_ms | 0.609 | 0.658 | 0.947 | 0.151 | 1.107 |

### First 20 rows

```text
         t      state  target_track_id  best_track_id  best_total  best_iou  best_distance  best_scale  best_confidence  best_appearance  best_appearance_used               reason
110.841112 REACQUIRED              1.0            1.0    0.673651  0.560357       0.999524    0.574381         0.856178         0.000000                 False reacquired_candidate
111.106838     LOCKED              1.0            1.0    0.897121  0.515111       0.998104    0.977245         0.764823         0.829135                  True   accepted_candidate
111.315464     LOCKED              1.0            1.0    0.906583  0.834244       0.999928    0.956340         0.791551         0.000000                 False   accepted_candidate
111.383012     LOCKED              1.0            1.0    0.896654  0.767093       0.999684    0.992048         0.838255         0.000000                 False   accepted_candidate
111.494997     LOCKED              1.0            1.0    0.936545  0.877760       0.999923    0.996458         0.848315         0.000000                 False   accepted_candidate
111.722432     LOCKED              1.0            1.0    0.843372  0.619218       0.998815    0.996458         0.812737         0.000000                 False   accepted_candidate
111.812427     LOCKED              1.0            1.0    0.869920  0.745477       0.999597    0.915106         0.798880         0.000000                 False   accepted_candidate
111.949457     LOCKED              1.0            1.0    0.891161  0.761624       0.999689    0.992047         0.812292         0.000000                 False   accepted_candidate
112.081138     LOCKED              1.0            1.0    0.899839  0.761487       0.999702    0.992047         0.874590         0.000000                 False   accepted_candidate
112.375380     LOCKED              1.0            1.0    0.869638  0.666741       0.999376    0.985906         0.897467         0.000000                 False   accepted_candidate
112.530738     LOCKED              1.0            1.0    0.945186  0.886713       0.999896    0.992047         0.894011         0.000000                 False   accepted_candidate
112.672637     LOCKED              1.0            1.0    0.973559  0.961394       0.999987    1.000000         0.904915         0.000000                 False   accepted_candidate
112.918781     LOCKED              1.0            1.0    0.957733  0.913368       0.999979    1.000000         0.908521         0.000000                 False   accepted_candidate
113.121447     LOCKED              1.0            1.0    0.954273  0.897447       0.999977    0.996458         0.927036         0.000000                 False   accepted_candidate
113.216468     LOCKED              1.0            1.0    0.958500  0.910147       0.999896    0.999113         0.923120         0.000000                 False   accepted_candidate
113.511419     LOCKED              1.0            1.0    0.872149  0.709728       0.999494    0.930663         0.881815         0.000000                 False   accepted_candidate
113.846021     LOCKED              1.0            1.0    0.922590  0.823967       0.999842    1.000000         0.874872         0.000000                 False   accepted_candidate
113.995008     LOCKED              1.0            1.0    0.872541  0.705309       0.999700    0.957462         0.860510         0.000000                 False   accepted_candidate
114.120505     LOCKED              1.0            1.0    0.888895  0.734412       0.999700    0.999113         0.853092         0.000000                 False   accepted_candidate
114.202024     LOCKED              1.0            1.0    0.942574  0.899170       0.999974    0.992047         0.844962         0.000000                 False   accepted_candidate
```

