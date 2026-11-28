# Humanoid Data Flywheel — đặc tả console offline [Đề xuất]

Ngày: 25/11/2026 · Phạm vi: thiết kế lại giao diện, giữ backend nguyên trạng. Hợp đồng bắt buộc: [api-contract.md](api-contract.md); khi hợp đồng lệch mã server, mã server là nguồn đúng. JSON mẫu chỉ mô tả hình dạng, không phải số cố định. URL tương đối so với server localhost; `data/...` dưới đây là URL chỉ mục trong hợp đồng.

## Định hướng sản phẩm [Đề xuất]

Console có hai vai trò ngang nhau: **quản lý và xử lý dữ liệu** cho đội và **trình bày bằng chứng Failure → Data** cho giám khảo. Không mặc định người dùng đang demo. Luồng dữ liệu chính: danh mục → nhập → xử lý/QA → xem tập và episode → phát hành/xuất → theo dõi job và nguồn gốc. Cho phép vào lại bất kỳ bước nào khi có dữ liệu; không giả định mọi tập đi đủ chuỗi. Các thao tác tạo, sửa, xóa, đổi tên dataset hay chỉnh nhãn/QA thủ công không có trong hợp đồng thì không hiển thị là chức năng khả dụng.

## 1. Cấu trúc và điều hướng

Bố cục desktop: thanh trên cùng gồm tên sản phẩm, chọn task, ngôn ngữ, sáng/tối, trạng thái khóa; menu trái 224 px, nội dung chính co giãn, chat phải 320 px có thể thu gọn. Ở cửa sổ hẹp, menu và chat thành ngăn kéo độc lập; nội dung và bảng cuộn ngang, không che hành động. Task đang chọn được giữ khi điều hướng trong phiên; đổi task xóa selection và dữ liệu riêng task cũ trước khi tải lại. Không suy ra task từ dữ liệu lần trước. Route không tồn tại hiện trang không tìm thấy với đường về tasks.

| Nhóm menu | Trang / hash route | Vai trò |
|---|---|---|
| Bắt đầu | `#/tasks` | Chọn task |
| Bắt đầu | `#/home` | Tổng quan sáu stage |
| Dữ liệu | `#/data` | Danh mục |
| Dữ liệu | `#/data/:id`, `#/data/:id/ep/:n` | Chi tiết tập, episode; breadcrumb từ danh mục |
| Dữ liệu | `#/jobs?panel=import`, `#/jobs?view=pipeline`, `#/jobs?panel=export` | Nhập, xử lý và xuất; dùng route jobs hiện có |
| Dữ liệu | `#/egoflow` | Pipeline video người |
| Dữ liệu | `#/qa` | Chất lượng |
| Vận hành | `#/jobs` | Job; gồm máy, pipeline và nhập dữ liệu |
| Thí nghiệm | `#/runs`, `#/eval`, `#/sim`, `#/sim/:i` | Train, đánh giá, thư viện mô phỏng |
| Failure → Data | `#/base`, `#/diagnose`, `#/loop`, `#/follow` | Baseline, chẩn đoán, vòng, ca đối chiếu |
| Kế hoạch & báo cáo | `#/design`, `#/cost`, `#/report` | Thiết kế, chi phí, báo cáo |

Giữ `#/jobs?view=machines`, `#/jobs?panel=import`, `#/jobs?panel=export`, `#/jobs?view=pipeline` và `#/jobs?job=<id>` để mở đúng phần; các liên kết stage từ server được tôn trọng nếu route hợp lệ. Bảng chuyển hướng bắt buộc (thay hash bằng `history.replaceState`, giữ query gốc như app cũ; với `loop?tab=cost` bỏ query):

| Route cũ | Route mới |
|---|---|
| `#/overview` | `#/home` |
| `#/process` | `#/jobs?view=pipeline` |
| `#/training` | `#/runs` |
| `#/agent` | `#/qa` |
| `#/data/nhap` | `#/jobs?panel=import` |
| `#/data/xuat` | `#/jobs?panel=export` |
| `#/home?s=...`, `#/home?tour=...` | `#/report`, giữ query gốc |
| `#/loop?tab=cost` | `#/cost` |

Nếu query cũ trùng tham số đích, xử lý theo router cũ, không làm mất tham số. Quyết định menu [Đề xuất]: giữ các nhóm ở bảng trên; đồng thời trang report, follow, base, design có sub-navigation chung “Báo cáo vòng”, để vẫn đi qua được toàn bộ nội dung báo cáo. Chi tiết không lặp lại trong menu; mục cha vẫn active. Chat là khung dùng chung, không phải route riêng.

## 2. Quy tắc dữ liệu và trạng thái chung

- Tải `data/tasks.json` và `/api/status` trước khi vẽ nội dung phụ thuộc task hoặc quyền. Mỗi task chỉ được dùng khóa `story.<key>` nằm trong hợp `tasks[].index[]` và `index[]` của round thuộc task đó. Nếu thiếu quyền dùng khóa, khối bị khóa theo phạm vi dữ liệu, kể cả khi `data/story.json` có giá trị. Không dùng số tray cho two_table. `data/sim.json`: nếu task không có `sim` trong index, chỉ hiện `teleop[]` lọc theo `teleop[].task` khớp task.
- Với tất cả round, lọc lại `withhold_eval` trước mọi render, tìm kiếm, biểu đồ, tooltip và chat context: loại khỏi `pair.runs`, `pair.comparisons` nếu variant hoặc baseline bị giữ, `follow.runs`, `demo.ladder.runs`, `demo.ladder.on_table_b.value`; xóa `follow.r3` và `demo.round1_reading`; trong khối `jig`, mục của run bị giữ trong `evals` chỉ còn `{run, role, status: "withheld"}`, và run bị bỏ khỏi `outcomes`, `rollouts`, `conditions`, `compare60.earlier` (DA-53). Thông tin train, cut, chi phí vẫn được phép hiện. Không suy ra kết quả bị giữ từ chênh lệch hay số tổng. Run trong `withhold_runs` (hiện là N, Hiếu 28/11/2026) đã bị server bỏ hẳn khỏi `data/story.json` và `data/tasks.json` ([hợp đồng API](api-contract.md) mục 1.3); giao diện không lọc thêm nhưng phải chịu được `after_round: null`.
- **Đang tải:** skeleton theo khối, `aria-busy`, không hiện số cũ của task khác. **Rỗng:** phân biệt mảng rỗng, `null`, không có file và dữ liệu chưa có quyền; hiện “Chưa có dữ liệu” hoặc `process[stage].missing[lang]`, không thay bằng 0. Nếu stage không có `process[n].missing`, hiện `process[n].how` có sẵn (lệnh/tài liệu), không coi sự vắng mặt là lỗi hay là đã xong; `remote` chỉ hiện khi có. **Lỗi:** giữ các khối đã tải độc lập; hiện thông báo dịch sẵn, HTTP code và `error` nguyên văn như dữ liệu, nút thử lại. 404 media là “Không có tệp trên máy”, không phải lỗi task. Không làm lộ đường dẫn khác chuỗi server đã trả.
- **Khóa:** sau khi GET `/api/status` trả `locked=true`, ẩn mọi hành động POST trừ chat, prewarm, connect khi `chat_on=true`; ẩn filesystem picker, kiểm thư mục, direct tool, trace và tải zip. GET được phép vẫn dùng. Nếu chưa biết trạng thái khóa, mặc định ẩn hành động ghi. Nếu server trả 403, cập nhật trạng thái và giải thích. Khóa dữ liệu do thiếu index khác với `--lock`: nêu rõ lý do, không giả là lỗi.
- Nguồn dữ liệu và đơn vị luôn kèm số liệu; giữ nguyên `source`, `quote`, `origin`, `kind` khi có, phân biệt đo/ước tính/trích dẫn. `success.source` và ngưỡng giả định phải nhìn thấy; không diễn đạt tương quan thành cải thiện đã chứng minh. Làm tròn chỉ ở hiển thị, không sửa dữ liệu. Các mảng mẫu có thể bị cắt, tuyệt đối không hard-code số từ mẫu.
- Các trạng thái trên áp dụng cho **mỗi khối** trang dưới đây; hàng “khóa” ghi bổ sung hành vi đặc thù. Tất cả nút điều hướng phải dùng route có thực, không tạo URL media bằng cách đoán đường dẫn.

## 3. Đặc tả từng trang

### Kiểm tra hợp đồng và khóa [Đề xuất]

Mọi URL gọi server trong §3 thuộc danh sách tại [api-contract.md](api-contract.md), kể cả các file `data/ds/<id>/...`, `/simmedia/...`, `/demomedia/...` và `/ego/`. Chuỗi `#/...` là route phía client, không phải endpoint. Không nối tên trường vào URL: ví dụ GET `/api/status`, rồi đọc `locked` và `chat_on` từ JSON. Không gọi URL tùy ý trong dữ liệu; chỉ dùng URL thuộc họ media/chỉ mục được hợp đồng cho phép, và không mở đường dẫn máy hoặc URL remote như endpoint. Trạng thái locked của mọi trang và chat được ghi ở từng mục dưới đây; quy tắc chung ở §2 luôn ưu tiên.

Ký hiệu: **T** = `data/tasks.json`, **C** = `data/catalog.json`, **S** = `data/story.json`, **M** = `data/sim.json`; `T.task` là phần tử task hiện tại, `T.round` là round liên kết. Truy cập S và M luôn theo §2. Những trường không được liệt kê là không được giả định.

### `#/tasks` — Chọn bài toán
Mục đích: cho người xem chọn đúng bài toán và hiểu điều kiện thành công.
- Thẻ task: T `tasks[].id`, `name[lang]`, `description[lang]`, `robot`, `model`, `simulator`, `success[lang]`, `success.source`; chọn thẻ vào home.
- Tóm tắt khả dụng: T `tasks[].rounds`, `process[].missing[lang]`, `catalog_totals` theo nhóm; phân biệt không có vòng với chưa tải.
- Tải/rỗng/lỗi theo §2; locked vẫn cho chọn và đọc, không có hành động ghi.

### `#/home` — Sáu stage
Mục đích: cho thấy tiến độ hiện tại và lối đi tiếp theo.
- Dải stage: `/api/status` `stages[].id,state,now,issue,how,jobs,link,task`; chỉ liên hệ với task đang chọn khi `task` khớp, thiếu task thì ghi phạm vi không xác định. Link hợp lệ dẫn đến trang tương ứng.
- Bối cảnh: T.task `name`, `description`, `stages[].vi/en`, `success`, `process[1..6].needs,missing,remote,how,logs,results`; số lượng catalog từ `catalog_totals`. Mỗi khối stage vắng `missing` không tự coi là đã hoàn thành.
- Job gần đây: `/api/status` `jobs[].id,kind,stage,state,created`; link tới jobs.
- Tải/rỗng/lỗi theo §2; locked chỉ đọc, stage không bị tự động gán blocked vì chế độ khóa.

### `#/data` — Trung tâm dữ liệu
Mục đích: tìm, xem và đi tới các công việc quản lý, xử lý dữ liệu theo task.
- Thanh đầu: tên, task và lối vào nhập `#/jobs?panel=import`, xử lý `#/jobs?view=pipeline`, xuất `#/jobs?panel=export`; chỉ hiện hành động khả dụng theo trường `locked` của `/api/status` và `/api/kinds`, danh sách export vẫn xem được khi khóa. Đây là điều hướng tới route hiện có, không tạo endpoint.
- Hai chế độ **danh sách / thư viện** cùng nguồn C `rows[].id,title,kind,group,data_type,task,episodes,frames,hours,status,view,licence,data_class,locations,thumbs`; tìm tên/id và lọc client theo trường có thật. Mỗi hàng/thẻ mở `#/data/:id`. Chỉ hiển thị ảnh từ URL thuộc hợp đồng; không mở URL từ xa. Nhãn laptop/từ xa/không rõ dựa trên `locations[].where,exists` và `view` khi có, không suy từ tên.
- Tổng theo task là T.task `catalog_totals`; C `generated,totals` là toàn catalog và phải ghi phạm vi, không cộng tập cha/con. T.task `catalog_rows` chỉ là tóm tắt, không thay catalog đầy đủ.
- Nguồn gốc: C `edges[]`, `rows[].parents,children`; cạnh chưa có đầu mút thì hiện id chưa có chi tiết, không bịa row.
- Tải/rỗng/lỗi theo §2; locked vẫn xem catalog và danh sách export, ẩn nhập/xử lý và tải ZIP.

### `#/data/:id` — Không gian làm việc của dataset
Mục đích: xem nội dung, chất lượng, nguồn gốc và công việc liên quan đến một tập.
- Header: C row theo `id`: `title,name,kind,group,data_type,task,episodes,frames,hours,fps,format,licence,data_class,status,qa,qa_counts,notes,view,unique,locations`; đường dẫn trả từ server hiển thị nguyên văn.
- Tab **Tổng quan / Nội dung / Chất lượng / Nguồn gốc / Công việc**. Tổng quan dùng C row. Nội dung dùng `data/ds/<id>/episodes.json`: robot `i,n,s,lv,seed,part,cut,out`, egocentric `id,title,s,qa,reasons,poster`; gallery dùng `data/ds/<id>/posters/<i>.jpg` với robot, poster được phép cho egocentric; danh sách lọc QA khi có trường. Mỗi episode mở `#/data/:id/ep/:n` với `n` tương ứng `i` robot hoặc `id` egocentric; encode tham số.
- Chất lượng: `data/ds/<id>/quality.json`, `qa.json` và các trường catalog QA có thật; Nguồn gốc: C `edges`, `parents`, `children` và `data/ds/<id>/method.json`; môi trường: `data/ds/<id>/env.json` nếu có. File không có là rỗng riêng khối; không suy ra chỉ số.
- Công việc: `/api/jobs` `id,kind,state,params,outputs,argv,created`; liên kết chắc chắn chỉ khi dữ liệu thực xác nhận quan hệ. Nếu so khớp chuỗi id/path trong params/outputs/argv như giao diện cũ, gắn nhãn “có thể liên quan”, không xem là lineage xác định; chọn job mở `#/jobs?job=<id>`.
- Lối xử lý/QA/xuất dẫn đến `#/jobs` tương ứng; không tự điền params từ dataset nếu không có mapping rõ, cho người dùng chọn trong form. Kind chỉ chạy nếu `/api/kinds` cho phép, args hợp lệ và không locked. Không có nút chỉnh sửa/xóa/đổi tên/gắn nhãn thủ công.
- Tải/rỗng/lỗi theo §2; id không có row hiện không tìm thấy; locked chỉ đọc, ẩn thao tác ghi, picker và tải zip.

### `#/data/:id/ep/:n` — Episode robot hoặc egocentric
Mục đích: xem nội dung episode và chất lượng cùng ngữ cảnh dataset.
- Đọc C row và `data/ds/<id>/episodes.json`; nhận diện theo `view` và trường của episode, không đoán từ task. Robot tìm `i` khớp `n`, egocentric tìm `id` khớp `n`; điều hướng trước/sau theo danh sách thực.
- Robot: `/api/episode?ds=<id>&ep=<n>` `ds,ep,n,fps,hz,t,action` với `names,v`, `state.hand,arm,leg,torso_rpy`; `/api/strip?ds=<id>&ep=<n>` và `data/ds/<id>/posters/<i>.jpg`; ECharts cho từng nhóm, bỏ null, không tự gán đơn vị. Media robot chỉ qua họ `/media/<ds>/<đường dẫn>` được hợp đồng và dữ liệu cho phép.
- Egocentric: `episodes.json` `id,title,s,qa,reasons,poster` và `data/ds/<id>/qa.json` khi có; `/api/poster?work=...&ep=...` và `/api/ego_strip?work=...&ep=...` chỉ khi có work/ep thật. Cho mở `/ego/` khi sẵn có; ảnh/video phải đã che danh tính. Không tạo URL video gốc; không đoán work hay ép id egocentric thành số.
- Tải/rỗng/lỗi theo §2; từng khối có 404 riêng, ảnh/video không có không che thông tin khác; locked vẫn xem GET được phép.

### `#/jobs` — Công việc, máy và nhập
Mục đích: theo dõi công việc và thực hiện các thao tác được server hỗ trợ.
- Danh sách/chi tiết/log: `/api/jobs?limit=...` và `/api/jobs/<id>` với `id,kind,stage,task,params,argv,state,rc,created,started,ended,seconds,outputs,note,tail`; `/api/jobs/<id>/log?offset=<n>` trả `text,offset,state`, nối theo offset và theo dõi khoảng 1 giây khi queued/running. Hủy bằng POST `/api/jobs/<id>/cancel`.
- Luồng dữ liệu: từ danh mục hoặc tập vào các panel import/pipeline/export; hiển thị tập hoặc nguồn đã chọn chỉ khi có mapping từ dữ liệu, nếu không yêu cầu người dùng chọn. Không suy diễn job–dataset chỉ từ tên. Sau job hiển thị output, link có căn cứ và log; catalog có thể chưa cập nhật, không giả định đã reindex.
- Tạo job: `/api/kinds` `kinds[].kind,stage,title,command,args,samples,available,reason,typical_seconds`, `remote`; dựng form theo mô tả `args`, gợi ý từ `samples[].params`, POST `/api/jobs` `{kind,params}`; lỗi 400 hiện thông điệp server. Không tạo nút nếu kind không available.
- Máy: `/api/status` `machines.laptop.slots`, `machines.rtx3060.tunnel`, `machines.colab.balance` và các trường máy thực có trong response; `/api/models` `tunnel,models,agent_model,agent_ready,nemotron,chat`. Không khẳng định máy online chỉ từ số dư cũ.
- Xuất: `/api/exports` `name,size,url,time`; mở `#/jobs?panel=export` để xem danh sách, chỉ tải `/api/exports/<file>.zip` khi không khóa. Nếu có thao tác tạo export, chỉ dùng kind được `/api/kinds` cung cấp.
- Nhập: khi mở khóa, `/api/fs?path=...`, `/api/dir_check?path=...`; upload video POST `/api/upload?dir=upload-YYYYMMDD-HHMM&task=<task>` với body là File/Blob bytes, `X-Filename` URL-encoded; trình duyệt tự gửi `Content-Length`, JS không tự đặt header bị cấm. Hiện lỗi 411 nếu server không nhận được độ dài; hiển thị `saved,dir,name,as,size`. Nhập/chạy pipeline dùng kind và args thực từ `/api/kinds`, không suy diễn endpoint.
- Tải/rỗng/lỗi theo §2; locked ẩn tạo/hủy job, import, picker, kiểm thư mục và nút tải zip; danh sách export, máy, job và log vẫn đọc được.

### `#/runs` — Train
Mục đích: so sánh tiến trình train và nguồn tập của các run được phép.
- S `runs[].job,branch,release,run_plan_id,step,max_steps,loss_last,loss,val,thr,vram,gn,groups_first,groups_last,argv`; ECharts dùng cặp `[step,value]`, bỏ điểm null, chú thích theo tên trường, không gán đơn vị chưa có.
- S `train_log_tail`, `vm_phases`; T.round `runs[].id,train_set,session,role`, `baseline,controls,max_steps` và S `demo.models.runs` nếu được cấp index. Train của run bị giữ kết quả vẫn có thể hiện.
- Tải/rỗng/lỗi theo §2; locked chỉ đọc, hành động job nếu có được ẩn.

### `#/eval` — Đánh giá
Mục đích: xem kết quả và so sánh có đối chứng trong phạm vi bằng chứng.
- Tray khi được phép: S `eval.source,policy`, `eval.levels[].level`, `eval.levels[].n`, `eval.levels[].successes`, `eval.levels[].succ`, `eval.levels[].wilson`, `eval.levels[].steps_pct`, `eval.stages`, `eval.failure_labels`, `eval.place_error_cm`, `eval.clusters`; S `pair.source,steps,runs[].run,n,successes,p,wilson,failures,step_pass,levels` và `comparisons[].tag,variant,baseline,n,variant_succ,baseline_succ,diff,ci,mcnemar_p,variant_only,baseline_only,outcome` sau lọc §2. Hiện n, khoảng tin cậy, nguồn; không tuyên bố thắng khi bằng chứng không đủ.
- Two_table: T.task `evals[].label,n,successes,level,sim_mode,origin,source` và `process[4].missing`; tỷ lệ có thể tính `successes/n` khi n > 0, luôn kèm n.
- Tải/rỗng/lỗi theo §2; khóa phạm vi story hiện lý do; khi `locked=true`, vẫn được đọc.

### `#/loop` — Failure → Data
Mục đích: theo dấu từ cụm lỗi tới dữ liệu chọn để train.
- T.round `title,baseline,after_round,controls,withhold_eval,cut`; S `round.source`, `round.plan`, `round.chain.targets`, `round.chain.generated`, `round.chain.recorded`, `round.chain.qa_pass`, `round.chain.quality`, `round.chain.selected`, `round.clusters[].id,stage,n,diagnosis,intervention,failures`, `round.per_case`, `round.planner_failures`; S `loop_chain`, `loop_detail.qa_pass,in_cut` chỉ khi được cấp index, ghi nhãn nguồn riêng, không ghép hai chuỗi.
- Phân biệt kế hoạch, đã tạo, QA và chọn; thông tin kết quả thi lại bị giữ không được hiện. T.task `process[6].missing` giải thích khi không có vòng.
- Tải/rỗng/lỗi theo §2; locked chỉ xem, không có nút tạo vòng nếu không có kind được phép.

### `#/cost` — Chi phí
Mục đích: trình bày chi phí có nguồn và giới hạn của phép so sánh.
- S `ledger`, `colab_balance`, `colab_sessions`; `/api/status` `machines.colab.balance,time,fresh` nếu có, đánh dấu cũ khi `fresh=false`. Không gán ledger chung cho task nếu chưa tách.
- S `demo.round_cost.kind,source,lines[].id,value,source,quote,total_cu,total_note,serve_waste,eval_client,usd_per_cu,usd_rate,total_usd`; S `demo.design.resource` gồm `kind,source,per_model_cu,min_cu,max_cu,value,gpu`; phân biệt đo và ước tính, không tự cộng các dòng mẫu thiếu.
- `/api/estimates` `path,label` là danh mục ước tính, không suy ra giá trị từ tên file. T.task `process[0].missing` giải thích thiếu tách task.
- Tải/rỗng/lỗi theo §2; locked vẫn đọc danh sách, không tải export bị cấm.

### `#/qa` — Kiểm chất lượng
Mục đích: xem quyết định QA và bằng chứng benchmark.
- `/api/works` `name,path,source_detail,episodes,tiers[].state,n,total,result,summary`; chọn work gọi `/api/work_episodes?work=...` với `episode_id,deid,frames,qa`. `/api/artifacts` `label,path,kind`; `/api/agent_stats` `runs,findings,last_job`; `/api/agent_result?out=...` dùng `out` đúng chuỗi server trả, chỉ trình bày nội dung thực có, không đoán schema.
- S `sources`, `heat` (các cặp mã kiểm tra và source; không suy ra số đếm), `reasons`, `h1m.qa`, `h1m.qa_reasons`, `qa_sample`, `demo.qa_bench.code_layer`, `agent_layer_nemotron`, `psi_data_bench` nếu được cấp; kèm source, ngày, mẫu và cận trên khi có; benchmark chưa chấm không biến thành kết quả.
- Tải/rỗng/lỗi theo §2; locked ẩn chạy QA và tải zip, kết quả GET vẫn xem.

### `#/sim` — Thư viện mô phỏng
Mục đích: tìm episode và dữ liệu mô phỏng theo task.
- M `source,sha8,parts,cuts,batch,episodes,round,format,teleop` theo §2; `teleop[].task` để lọc, `episodes[].i,video,poster,seed,level,cluster` để xem và lọc. Chọn episode bằng `episodes[].i` cho `#/sim/:i`; không dùng vị trí mảng làm id. Không giả định các thuộc tính khác.
- Tải/rỗng/lỗi theo §2; nếu chỉ có teleop được phép, nêu rõ phần còn lại không khả dụng; locked đọc được.

### `#/sim/:i` — Chi tiết mô phỏng
Mục đích: quan sát một episode trong thư viện được phép.
- M `episodes[]`: tìm phần tử có `i` khớp tham số `:i`, sau đó dùng `video,poster,seed,level,cluster` theo §2; với đường dẫn media tương đối có trong dữ liệu, dùng tiền tố `/simmedia/` theo hợp đồng và giao diện cũ. Không suy ra đường dẫn khi thiếu trường. Hiện `source,sha8` và điều khiển video nếu có.
- Tải/rỗng/lỗi theo §2; id không có trong danh sách hoặc không được cấp `sim` hiện không khả dụng; locked vẫn xem media được phép.

### `#/egoflow` — Xử lý video người
Mục đích: theo dõi các tầng xử lý và xem bản đã che danh tính.
- `/api/works` `name,path,source_detail,episodes,tiers[].state,n,total,result,summary`; chọn work gọi `/api/work_episodes?work=...` `episode_id,deid,frames,qa`.
- `/api/poster?work=...&ep=...&w=...`, `/api/ego_strip?work=...&ep=...&n=...` chỉ cho episode có định danh thực; link `/ego/` explorer. S `h1m` gồm `clips,hours,exported,exported_hours,decisions,qa,fps,resolutions,seconds_median,hands_visible_median,hands_visible_ge_95,exported_hands_visible_ge_95,bone_cv_median,qa_reasons` nếu được cấp.
- Tải/rỗng/lỗi theo §2; 404 ảnh nghĩa là chưa có video đã che, không thử video gốc; locked ẩn nhập/chạy, vẫn xem ảnh an toàn.

### `#/base` — Baseline và đối chứng
Mục đích: xác định model, tập train và đối chứng trước khi đọc kết quả.
- T.round `runs[].id,train_set,session,role`, `baseline,controls`; S `demo.models.runs` các trường `data,episodes,base_episodes,targeted_episodes,human_video,human_clips,round1` và `cites` nếu được cấp. S `pair.runs` và `comparisons` sau lọc §2, nêu nguồn `pair.source` và cỡ mẫu.
- Tải/rỗng/lỗi theo §2; không có round hiện T.task `process[6].missing`; locked chỉ đọc.

### `#/design` — Thiết kế thí nghiệm
Mục đích: giải thích đầu vào, đầu ra, môi trường và nguồn lực.
- T.task `description,robot,model,simulator,stages,stages_source,success,scorer_config,process`; S `demo.design.input,output,environment,devices,resource,source,unsourced` nếu được cấp; mỗi mục hiển thị `kind,value,source,quote` khi có.
- Tải/rỗng/lỗi theo §2; dữ liệu không nguồn được gắn nhãn thiếu bằng chứng, không bù số; locked chỉ đọc.

### `#/diagnose` — Chẩn đoán
Mục đích: phân biệt lỗi hệ thống, policy và trường hợp chưa rõ trước khi chọn dữ liệu.
- T.task `clusters.origin`, `clusters.items[].id,checkpoint,level,step,stage,members,source,quote`, `clusters.diagnosis`, `clusters.diagnosis_source`, `clusters.diagnosis_quote`, `process[5].missing`; S `round.clusters`, `demo.diagnose.checks[].id,value,source,quote`, `to_data,tickets,cost_cu`, `source` nếu được cấp.
- Giữ `unknown`/`not_judged` là chưa rõ, không suy luận yếu kỹ năng nếu thiếu trace. Link sang loop chỉ khi có dữ liệu và round phù hợp.
- Tải/rỗng/lỗi theo §2; locked ẩn chạy kiểm tra, dữ liệu đã có vẫn đọc.

### `#/follow` — Theo một ca
Mục đích: đối chiếu các model trên cùng level và seed đã ghi.
- S `follow.source,level,seed,tol.distance_m,yaw_error_deg,runs` và từng run `success,failure,reach_b,distance_m,yaw_error_deg`, sau lọc §2; hiển thị các ngưỡng và giá trị với đơn vị m/độ, không suy ra thành công chỉ từ một trường. T.round `follow.level,seed` làm ngữ cảnh.
- Tải/rỗng/lỗi theo §2; không có case hiện rỗng, không thay bằng video minh họa; locked đọc được.

### `#/report` — Báo cáo demo
Mục đích: kể lại kết quả, đối chứng, giới hạn và chi phí có bằng chứng.
- Các khối từ T.task `name,success,process[n].missing`, T.round `title,baseline,controls`; S `pair` so sánh sau lọc, `round.chain`, `demo.fail_share`, `demo.round_cost`, `demo.qa_bench`, `demo.design.unsourced` nếu được cấp. Mỗi chỉ số liên kết source, n và phạm vi.
- Video minh họa S `demo.success_clip.model,success,provenance,deck_caption,level,seed,note,source` và URL chỉ khi server trả đường dẫn thuộc `/demomedia/...` hợp lệ; null level/seed hiển thị chưa biết, không coi clip là video rollout của phép so sánh. `/api/exports` `name,size,url,time` liệt kê export; chỉ mở URL tải được hợp đồng cho phép khi không khóa.
- Tải/rỗng/lỗi theo §2; locked ẩn tải zip, báo cáo đọc được.

### Chat phải — trợ lý làm việc theo ngữ cảnh
Mục đích: giúp người dùng hiểu dữ liệu, tìm bằng chứng và mở đúng trang, có khả năng quan sát tool và giới hạn của câu trả lời.
- Bố cục: panel phải 320–400 px co giãn/thu gọn, có nút đóng và mở rõ ràng; trên màn hình hẹp là drawer không che mất đường quay lại. Header có tên trợ lý, trạng thái, provider/model và nút mở rộng/thu gọn. Ngữ cảnh hiển thị route và selection hiện tại, có thể bỏ chọn; khi đổi task xóa selection cũ. Gợi ý câu hỏi theo trang là chuỗi i18n, bấm chỉ điền ô nhập, không tự gửi.
- Composer nhiều dòng, Enter gửi và Shift+Enter xuống dòng, có nút gửi/dừng; không gửi ô rỗng; chỉ một lượt đang chạy, hủy fetch khi dừng. Hội thoại gồm câu hỏi, câu trả lời streaming, nhãn thời gian/đang trả lời và cảnh báo rõ nếu gián đoạn. Tin mới không giật cuộn khi người dùng đang đọc tin cũ; có nút về tin mới. Nút hội thoại mới xóa lịch sử trong bộ nhớ, reset conversation_id; không ghi lịch sử vào localStorage.
- Nguồn trạng thái: GET `/api/status` trường `locked,chat_on`; GET `/api/models` `tunnel,models,agent_model,agent_ready,nemotron,chat.provider,chat.model,chat.hosted`; GET `/api/tools?route=...` `name,description,parameters,slash`. Không coi tunnel down là tất cả model đều offline; nêu đúng dữ liệu backend. Khi đang tải trạng thái, tạm khóa composer; `chat_on=false` giải thích chat tắt. `prewarm`/`connect` chỉ hiển thị khi được phép; GET model lại sau lỗi/kết nối.
- Request: POST `/api/chat` `{conversation_id,messages,context:{route,selection}}`; đầu tiên bỏ conversation_id, về sau lấy từ `trace_start`, chỉ gửi tối đa 8 tin gần nhất và selection được phép. Dùng fetch SSE, xử lý event tách qua chunk và đóng kết nối, không EventSource; không tự gọi model/URL bên ngoài.
- Minh bạch tool và nguồn: `tool_start` tạo dòng công việc theo `call_id`; `tool_result` cập nhật `ok,name,ms,ui` theo cùng id, cho mở/thu kết quả, chỉ render kiểu `ui` được hỗ trợ an toàn; `navigate` là nút gợi ý, không tự điều hướng. `token.text` nối vào câu trả lời; `done.numbers,unverified` gắn nhãn số chưa kiểm, hiển thị nguồn khi `ui` hoặc nội dung tool có nguồn thực, không tạo citation giả. Không render HTML không tin cậy.
- Trạng thái: đang kết nối/đợi token/đang gọi tool/đang trả lời/hoàn tất/dừng/lỗi phân biệt rõ; `error.message` hiện nguyên văn kèm thông báo i18n, nếu `fallback=slash` chỉ cho direct `/api/tool?name=...&args=...&route=...` khi không khóa, encode JSON args. Retry là hành động chủ động của người dùng, không gửi lại tự động. `/api/chat/bench` 404 là chưa có; traces chỉ khi không khóa.
- Locked: nếu `chat_on=true` vẫn cho `/api/chat`, `/api/models/prewarm`, `/api/models/connect`; ẩn direct `/api/tool` và `/api/chat/traces`. Nếu `chat_on=false` vô hiệu composer và các POST chat. Tool qua chat theo hợp đồng, không hứa rằng tất cả tool thực thi được; UI phản ánh lỗi server. Tuân thủ lọc withhold và phạm vi task như §2.

Quyết định dữ liệu [Đề xuất]: giữ `story.heat` trong QA như trên khi task có quyền truy cập; không dùng `story.ds` vì là bản catalog lặp, trang dữ liệu lấy trực tiếp `data/catalog.json`. Kiểm tra giao diện cũ trong worktree: không tìm thấy tham chiếu rõ ràng tới `story.heat` hay `story.ds`; không suy ra chức năng cũ từ hai tên trùng trong biến cục bộ.

## 4. Kịch bản demo 5 phút

Chuẩn bị offline: index và media phải có trên laptop; mở khóa/khóa theo cấu hình demo, kiểm tra status trước. Không chờ job mới hay phụ thuộc mạng. Nếu khối không được cấp index hoặc file vắng, nói rõ giới hạn và đi tiếp; không thay bằng số mẫu.

| Thời gian | Trang | Lời dẫn và thao tác |
|---|---|---|
| 0:00–0:35 | tasks → home | Chọn tray, giới thiệu Unitree G1/Ψ₀, điều kiện thành công có nguồn, sáu stage và trạng thái thực. |
| 0:35–1:25 | eval → follow | Xem kết quả cùng n, khoảng tin cậy và so sánh đối chứng; nếu có case cùng seed thì so sánh khoảng cách/góc. Không kết luận model cải thiện nếu dữ liệu không chứng minh. |
| 1:25–2:15 | diagnose | Chỉ cụm và kiểm tra có nguồn, phân biệt policy với chưa rõ; chuyển sang loop. |
| 2:15–3:05 | loop → base | Theo chuỗi mục tiêu → tạo → QA → chọn; giải thích tập baseline, đối chứng và thông tin train. Không trình bày kết quả bị giữ. |
| 3:05–3:45 | data → qa | Xem loại dữ liệu, nguồn gốc và QA; nhắc egocentric chỉ xem bản che danh tính. |
| 3:45–4:20 | cost | Phân biệt CU đo/ước tính, nguồn, phạm vi và phần chi phí chưa có. |
| 4:20–5:00 | tasks → diagnose hoặc eval của two_table | Cho thấy hai bàn có kết quả trích dẫn và chẩn đoán chưa rõ do thiếu trace; kết thúc bằng report hoặc câu hỏi trong chat nếu còn thời gian. |

Không hứa chọn tối ưu giữa egocentric, teleop, synthetic nếu chưa có dữ liệu chi phí và lựa chọn có nguồn cho từng loại.

## 5. Design tokens và tương tác

CSS custom properties; dark áp qua `data-theme=dark`. Tất cả là tài nguyên local; dùng system font `system-ui, -apple-system, Segoe UI, sans-serif`, monospace `ui-monospace, monospace`; không tải font. Màu trạng thái luôn đi kèm nhãn/icon, không chỉ dựa vào màu.

| Token | Light | Dark | Dùng |
|---|---|---|---|
| `--bg` | `#f5f7fa` | `#101720` | Nền |
| `--surface` | `#ffffff` | `#1a2532` | Card, ngăn |
| `--surface-muted` | `#edf2f7` | `#243242` | Nền phụ |
| `--text` | `#172333` | `#edf3f8` | Chữ chính |
| `--text-muted` | `#4b5f73` | `#b9c8d8` | Chữ phụ |
| `--border` | `#c7d2dd` | `#4c5f72` | Viền |
| `--accent` | `#1458a6` | `#91c5ff` | Link, focus |
| `--success` | `#176b45` | `#82dfac` | done/ok |
| `--warning` | `#815600` | `#f4ce70` | waiting/ước tính |
| `--danger` | `#a12932` | `#ffadb4` | failed/blocked |
| `--info` | `#315c85` | `#a5cef5` | Thông tin |

Chữ: 12 px metadata, 14 px bảng/nội dung, 16 px body chính, 20 px tiêu đề khối, 28 px tiêu đề trang; line-height 1.45–1.6. Khoảng cách 4/8/12/16/24/32 px; bo 4 px cho badge, 8 px cho input/nút, 12 px cho card; viền 1 px, focus ring 2 px accent. Nút tối thiểu 40 px cao; target bàn phím, thứ tự focus rõ, biểu đồ có bảng số thay thế, trạng thái tải thông báo qua live region. Kiểm tương phản chữ thường tối thiểu 4.5:1 và focus 3:1 trên nền sử dụng thực tế; điều chỉnh token nếu kiểm thử không đạt.

ECharts chỉ từ `web/vendor/echarts.min.js`, resize khi đổi panel/theme, destroy khi rời trang; hỗ trợ bảng dự phòng. JS thuần + CSS, không framework/npm/build/CDN; fetch tương đối, không thêm server, CSDL hoặc tài nguyên mạng. Chỉ `localStorage` cho theme, ngôn ngữ, tab xem; không lưu payload, lịch sử chat hay dữ liệu task ở đó.

## 6. Quy ước vi/en

- Mọi chuỗi giao diện do sản phẩm viết, kể cả menu, nút, label biểu đồ, trạng thái, placeholder, aria-label, thông báo lỗi, title và đơn vị định dạng, nằm trong file i18n local theo key ổn định; đủ `vi` và `en`, kiểm tra key thiếu khi phát triển. Chuyển ngôn ngữ cập nhật toàn trang và chat mà không reload dữ liệu.
- Dữ liệu do backend cung cấp không dịch bằng cách sửa nội dung: chọn `name[lang]`, `description[lang]`, `word[lang]`, `success[lang]`, `stages[].vi/en`, `missing[lang]`, `title[lang]` khi có. Chuỗi chỉ có một ngôn ngữ, ví dụ log, tên tập, `error`, `source`, `quote`, command và id, hiển thị nguyên văn, có nhãn i18n “nguồn gốc”; không giả rằng đã dịch. Mã stage/trạng thái có bản dịch i18n và giữ mã gốc trong chi tiết khi hữu ích.
- `Intl.NumberFormat`, `Intl.DateTimeFormat` theo locale; giữ thời gian và múi giờ theo dữ liệu, không tự suy diễn; null hiển thị nhãn i18n “Chưa có” / “Not available”, số 0 vẫn là 0. Tên model, id, seed, đường dẫn, mã lỗi và CU là dữ liệu bất biến.

## 7. Cần thêm API / dữ liệu

Các mục dưới đây là khoảng trống, không thuộc phạm vi thay backend hiện tại; giao diện hiển thị thiếu thay vì giả lập.

1. Giá và năng lực thu theo từng loại egocentric/teleop/synthetic, phương án được chọn, lý do và đối chứng cùng phạm vi; chưa thể khẳng định tối ưu chi phí.
2. Ledger tách theo task và nhân công tạo dữ liệu; nguồn chi phí test còn thiếu theo `demo.design.unsourced`.
3. Trace và kết quả chấm từng bước two_table; `not_judged` không thể biến thành chẩn đoán xác định. Kết quả vòng two_table khi thực sự có.
4. API sửa metadata, đổi tên/xóa dataset, chỉnh nhãn hoặc quyết định QA thủ công nếu sản phẩm cần; hợp đồng hiện tại không có.
5. Khóa liên kết dataset–work–job chính xác và tín hiệu index cập nhật sau job nếu backend chưa cung cấp; trước mắt phải đánh dấu liên kết suy đoán.
6. API hoặc dữ liệu có nguồn cho những thống kê/video không được liệt kê trong hợp đồng, đặc biệt các hàng bị `demo.ladder.omitted`; kết quả `withhold_eval` chỉ hiển thị sau khi chính sách và hợp đồng cho phép.
