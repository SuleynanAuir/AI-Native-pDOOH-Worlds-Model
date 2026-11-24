// Bounded CSV parser: quoted commas/newlines and escaped quotes are preserved.
export function parseCalibrationCSV(text,currency){
 const rows=[];let row=[],cell='',quoted=false
 for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){cell+='"';i++}else quoted=!quoted}else if(c===','&&!quoted){row.push(cell);cell=''}else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell);if(row.some(x=>x.trim()))rows.push(row);row=[];cell=''}else cell+=c}
 if(quoted)throw Error('CSV引号未闭合');row.push(cell);if(row.some(x=>x.trim()))rows.push(row)
 const headers=(rows.shift()||[]).map(x=>x.replace(/^\uFEFF/,'').trim())
 const required=['screen_id','test_exposures','test_orders','control_exposures','control_orders','order_value','margin','currency','period','source']
 if(new Set(headers).size!==headers.length||required.some(k=>!headers.includes(k)))throw Error('CSV表头缺失或重复，请使用模板字段')
 const out={};for(const row of rows){if(row.length!==headers.length)throw Error('CSV列数与表头不一致');const r=Object.fromEntries(headers.map((k,i)=>[k,row[i].trim()]));if(!r.screen_id||out[r.screen_id])throw Error('屏幕ID为空或重复');if(r.currency!==currency)throw Error('历史数据币种必须与当前预算币种一致');for(const k of ['test_exposures','test_orders','control_exposures','control_orders','order_value','margin','extra_cost']){if(k==='extra_cost'&&!r[k])r[k]='0';if(!r[k]||!Number.isFinite(Number(r[k])))throw Error('历史数据数值无效：'+k);r[k]=Number(r[k])}out[r.screen_id]=r}
 if(!rows.length||rows.length>10000)throw Error('请选择1–10000条逐屏历史记录');return out
}
