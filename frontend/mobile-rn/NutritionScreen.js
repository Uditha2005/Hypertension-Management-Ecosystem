import React, { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Image, Pressable, Text, TextInput, View } from "react-native";
import * as ImagePicker from "expo-image-picker";

const MEALS = ["Breakfast", "Lunch", "Dinner", "Snacks"];
const today = () => new Date().toISOString().slice(0, 10);
const freshEntry = (day, meal) => ({ day, meal, fdc_id: "", description: "", quantity: "100", unit: "g", supported_units: ["g"] });

export default function NutritionScreen({ apiBase, colors, onBack }) {
  const [days, setDays] = useState([today()]);
  const [day, setDay] = useState(today());
  const [meal, setMeal] = useState("Breakfast");
  const [entries, setEntries] = useState([]);
  const [age, setAge] = useState("60");
  const [bmi, setBmi] = useState("");
  const [requirements, setRequirements] = useState("");
  const [medications, setMedications] = useState("");
  const [query, setQuery] = useState("");
  const [foods, setFoods] = useState([]);
  const [photo, setPhoto] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [recordId, setRecordId] = useState("");
  const [dashResults, setDashResults] = useState({});
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("Checking nutrition service…");
  const [error, setError] = useState("");
  const [view, setView] = useState("plan");
  const C = colors;
  const styles = useMemo(() => ({
    card: { backgroundColor:C.white, borderColor:C.border, borderWidth:1, borderRadius:16, padding:15, gap:12 },
    title: { color:C.ink, fontSize:25, fontWeight:"800" },
    sub: { color:C.muted, fontSize:13, lineHeight:19 },
    label: { color:C.ink, fontWeight:"700", fontSize:12, marginBottom:5 },
    input: { backgroundColor:C.bg, color:C.ink, borderColor:C.border, borderWidth:1, borderRadius:9, padding:11, minHeight:42 },
    button: { backgroundColor:C.green, borderRadius:10, padding:12, alignItems:"center", justifyContent:"center", minHeight:43 },
    buttonText: { color:"#fff", fontWeight:"800", fontSize:13 },
    chip: { paddingVertical:8, paddingHorizontal:11, borderRadius:20, backgroundColor:C.bg, borderWidth:1, borderColor:C.border },
    chipOn: { backgroundColor:C.mint, borderColor:C.green },
    chipText: { color:C.ink, fontWeight:"700", fontSize:12 },
    muted: { color:C.muted, fontSize:11, lineHeight:16 },
  }), [C]);
  async function request(path, method="GET", body) {
    const response = await fetch(`${apiBase}${path}`, { method, headers:{"Content-Type":"application/json"}, body:body ? JSON.stringify(body) : undefined });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Nutrition request failed (${response.status})`);
    return data;
  }
  useEffect(() => { request("/health").then(data => setStatus(`${data.service || "Nutrition API"} connected`)).catch(e => setStatus(e.message)); }, [apiBase]);
  const activeEntries = entries.filter(e => e.day === day && e.meal === meal);
  const update = (index, field, value) => { setEntries(current => current.map((e,i) => i === index ? {...e,[field]:value} : e)); setAnalysis(null); };
  async function search() {
    setError(""); setFoods([]); if (!query.trim()) return setError("Enter a food to search.");
    setLoading(true); try { const result = await request(`/foods/search?query=${encodeURIComponent(query.trim())}&limit=10`); setFoods(result.foods || []); if (!(result.foods || []).length) setStatus("No matching USDA foods. Try a broader search."); }
    catch(e) { setError(e.message); } finally { setLoading(false); }
  }
  async function addFood(food) {
    setLoading(true); setError(""); try {
      const d = await request(`/foods/${encodeURIComponent(food.fdc_id)}/details`);
      const unit = d.supported_units?.includes("g") ? "g" : d.supported_units?.[0];
      if (!unit) throw new Error("This USDA record has no supported quantity unit.");
      const quantity = unit === "g" ? "100" : d.serving_size_unit?.toLowerCase() === "g" && d.serving_size ? String(d.serving_size) : "1";
      setEntries(current => [...current, {...freshEntry(day,meal), fdc_id:String(food.fdc_id), description:d.description, quantity, unit, supported_units:d.supported_units, serving_size:d.serving_size, serving_size_unit:d.serving_size_unit}]); setAnalysis(null); setFoods([]); setQuery("");
    } catch(e) { setError(e.message); } finally { setLoading(false); }
  }
  async function choosePhoto(camera) {
    const permission = camera ? await ImagePicker.requestCameraPermissionsAsync() : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) return setError("Camera or photo-library permission is required.");
    const result = camera ? await ImagePicker.launchCameraAsync({ mediaTypes:["images"], allowsEditing:true, quality:.75, base64:true }) : await ImagePicker.launchImageLibraryAsync({ mediaTypes:["images"], allowsEditing:true, quality:.75, base64:true });
    if (!result.canceled) { const asset=result.assets[0]; if ((asset.fileSize || 0) > 8*1024*1024) return setError("Choose an image smaller than 8 MB."); setPhoto(asset); setSuggestions([]); setError(""); }
  }
  async function identify() {
    if (!photo?.base64) return setError("Choose a meal photo first."); setLoading(true); setError("");
    try { const mime=photo.mimeType || (photo.uri.toLowerCase().endsWith(".png") ? "image/png":"image/jpeg"); const result=await request("/foods/identify-image","POST",{image_data_url:`data:${mime};base64,${photo.base64}`,meal_context:meal}); setSuggestions((result.foods || []).map((x,i)=>({...x,key:`${Date.now()}-${i}`,name:x.food_name,grams:String(Math.round(x.estimated_quantity_g)),selected:true}))); setStatus(result.message || "Review each suggestion and portion."); }
    catch(e) { setError(e.message); } finally { setLoading(false); }
  }
  async function addSuggested() {
    setLoading(true); setError(""); const resolved=[];
    try { for (const s of suggestions.filter(x=>x.selected)) { const searchResult=await request(`/foods/search?query=${encodeURIComponent(s.name)}&limit=5`); const food=searchResult.foods?.[0]; if (!food) continue; const d=await request(`/foods/${food.fdc_id}/details`); const unit=d.supported_units?.includes("g") ? "g" : d.supported_units?.[0]; if (!unit) continue; let quantity=String(Number(s.grams)); if (unit==="serving" && d.serving_size_unit?.toLowerCase()==="g" && d.serving_size) quantity=String(Number(s.grams)/d.serving_size); resolved.push({...freshEntry(day,meal),fdc_id:String(food.fdc_id),description:d.description,quantity,unit,supported_units:d.supported_units,serving_size:d.serving_size,serving_size_unit:d.serving_size_unit}); } setEntries(current=>[...current,...resolved]); setAnalysis(null); setSuggestions([]); setPhoto(null); if(!resolved.length) setError("No photo suggestions matched a USDA record. Add foods through search."); }
    catch(e) { setError(e.message); } finally { setLoading(false); }
  }
  async function analyze() {
    setError(""); if (!entries.length) return setError("Add at least one food.");
    for (const e of entries) { const q=Number(e.quantity), max=e.unit==="g"?5000:e.unit==="kg"?5:50; if (!e.fdc_id || !e.supported_units?.includes(e.unit) || !q || q<=0 || q>max) return setError(`Check the USDA selection, unit, and portion for ${e.description || "a food"}.`); }
    const n=Number(age); if(!Number.isFinite(n)||n<=18||n>=120) return setError("Enter an age between 19 and 119.");
    setLoading(true); try { const payload={entries:entries.map(({day,meal,description,fdc_id,quantity,unit})=>({day,meal,description,fdc_id:Number(fdc_id),quantity:Number(quantity),unit})),selected_days:days,personal_profile:{age_years:n,bmi:bmi?Number(bmi):null,dietary_requirements:requirements.split(",").map(x=>x.trim()).filter(Boolean),confirmed_medications:medications.split(",").map(x=>x.trim()).filter(Boolean),dietary_preferences:[],dietary_restrictions:[],allergies:[],preferred_foods:[],nutrition_goal:"dash_style"},full_day_intake:false}; const result=await request("/meal-plans/analyze","POST",payload); setAnalysis(result); setDashResults({}); setView("results");
      try { const saved=await request("/meal-records","POST",{meal_date:days[0],meals:payload.entries,analysis:result}); setRecordId(saved?.record?.record_id || ""); } catch(_) { setRecordId(""); }
      const grams = e => { const q=Number(e.quantity); if(e.unit==="g")return q;if(e.unit==="kg")return q*1000;if(e.unit==="serving"&&e.serving_size_unit?.toLowerCase()==="g"&&Number(e.serving_size)>0)return q*Number(e.serving_size);return null; };
      for(const d of days){ const items=entries.filter(e=>e.day===d&&e.description.trim()&&grams(e)!=null).map(e=>({food_name:e.description,quantity_grams:grams(e)})); if(!items.length){setDashResults(x=>({...x,[d]:{status:"unavailable",message:"No confirmed gram quantities are available for optimization."}}));continue;} try{const optimized=await request("/dash/optimize-current-day","POST",{items});setDashResults(x=>({...x,[d]:optimized}));}catch(e){setDashResults(x=>({...x,[d]:{status:"unavailable",message:e.message}}));} }
    } catch(e) { setError(e.message); } finally { setLoading(false); }
  }
  async function loadHistory() { setLoading(true); setError(""); try { const r=await request("/meal-records?limit=30"); setHistory(r.records || []); setView("history"); } catch(e) { setError(e.message); } finally { setLoading(false); } }
  async function feedback(title, rating) { if(!recordId) return setError("Feedback is available after the meal record has been saved."); try { await request(`/meal-records/${encodeURIComponent(recordId)}/feedback?profile_id=local-demo` ,"POST",{suggestion_title:title,rating,comment:""}); setStatus("Feedback saved."); } catch(e) { setError(e.message); } }
  function addDay() { const next=new Date(`${days[days.length-1]}T12:00:00`); next.setDate(next.getDate()+1); const value=next.toISOString().slice(0,10); setDays(current=>[...current,value]); setDay(value); }

  const card=styles.card;
  return <View style={{gap:14,paddingBottom:24}}>
    <View style={{gap:7}}><Text style={{color:C.green,fontSize:11,fontWeight:"800",letterSpacing:1}}>COMPONENT 03 · NUTRITION CARE</Text><Text style={styles.title}>Personalized meal assessment</Text><Text style={styles.sub}>Build meals, check nutrient totals and review hypertension focused DASH guidance.</Text><Text style={styles.muted}>{status}</Text></View>
    {!!error && <View style={{backgroundColor:C.redBg,borderColor:C.red,borderWidth:1,borderRadius:10,padding:12}}><Text style={{color:C.red,fontSize:13}}>{error}</Text></View>}
    {loading && <View style={{flexDirection:"row",gap:8,alignItems:"center"}}><ActivityIndicator color={C.green}/><Text style={styles.muted}>Working with nutrition service…</Text></View>}
    <View style={{flexDirection:"row",gap:8}}>{[["plan","Meal plan"],["results","Results"],["history","History"]].map(([v,label])=><Pressable key={v} onPress={()=>v==="history"?loadHistory():setView(v)} style={[styles.chip,view===v&&styles.chipOn]}><Text style={styles.chipText}>{label}</Text></Pressable>)}</View>
    {view==="plan" && <>
      <View style={card}><Text style={{color:C.ink,fontWeight:"800",fontSize:17}}>Assessment details</Text><Field label="Age (years)" value={age} onChangeText={setAge} styles={styles} keyboardType="numeric"/><Field label="BMI (optional)" value={bmi} onChangeText={setBmi} styles={styles} keyboardType="decimal-pad"/><Field label="Dietary requirements (comma separated)" value={requirements} onChangeText={setRequirements} styles={styles} placeholder="e.g. lower sodium, vegetarian"/><Field label="Confirmed medicine ingredients (optional)" value={medications} onChangeText={setMedications} styles={styles} placeholder="Only ingredients verified from packaging or prescription"/><Text style={styles.muted}>These details are sent for this assessment and are not saved as a personal profile.</Text><Text style={{color:C.ink,fontWeight:"700"}}>Plan days</Text><View style={{flexDirection:"row",flexWrap:"wrap",gap:7}}>{days.map(d=><Pressable key={d} onPress={()=>setDay(d)} style={[styles.chip,day===d&&styles.chipOn]}><Text style={styles.chipText}>{d}</Text></Pressable>)}</View><Pressable onPress={addDay} style={[styles.button,{backgroundColor:C.mint}]}><Text style={[styles.buttonText,{color:C.green}]}>Add next day</Text></Pressable></View>
      <View style={card}><Text style={{color:C.ink,fontWeight:"800",fontSize:17}}>Build meals</Text><Text style={styles.muted}>Selected day: {day}</Text><View style={{flexDirection:"row",flexWrap:"wrap",gap:7}}>{MEALS.map(m=><Pressable key={m} onPress={()=>setMeal(m)} style={[styles.chip,meal===m&&styles.chipOn]}><Text style={styles.chipText}>{m}</Text></Pressable>)}</View><Field label="Search USDA foods" value={query} onChangeText={setQuery} styles={styles} placeholder="Oats, rice, eggs, vegetables…"/><Button title="Search foods" onPress={search} styles={styles}/>{foods.map((f,i)=><Pressable key={`${f.fdc_id}-${i}`} onPress={()=>addFood(f)} style={{paddingVertical:8,borderTopWidth:1,borderColor:C.border}}><Text style={{color:C.ink,fontWeight:"700"}}>{f.description}</Text><Text style={styles.muted}>{f.data_type} · USDA {f.fdc_id} · Tap to add</Text></Pressable>)}<View style={{flexDirection:"row",gap:8}}><Button title="Take photo" onPress={()=>choosePhoto(true)} styles={styles} flex/><Button title="Upload photo" onPress={()=>choosePhoto(false)} styles={styles} flex/></View>{photo&&<><Image source={{uri:photo.uri}} style={{width:"100%",height:180,borderRadius:12}}/><Button title="Identify foods in photo" onPress={identify} styles={styles}/></>}{suggestions.map(s=><View key={s.key} style={{gap:7,padding:10,backgroundColor:C.bg,borderRadius:10}}><Text style={{color:C.ink,fontWeight:"800"}}>{s.food_name} · {s.confidence} confidence</Text><Text style={styles.muted}>{s.notes || "Photo portions are approximate; review before adding."}</Text><Field label="Correct food name" value={s.name} onChangeText={v=>setSuggestions(a=>a.map(x=>x.key===s.key?{...x,name:v}:x))} styles={styles}/><Field label="Estimated portion (g)" value={s.grams} onChangeText={v=>setSuggestions(a=>a.map(x=>x.key===s.key?{...x,grams:v}:x))} styles={styles} keyboardType="decimal-pad"/><Pressable onPress={()=>setSuggestions(a=>a.map(x=>x.key===s.key?{...x,selected:!x.selected}:x))}><Text style={{color:C.green,fontWeight:"800"}}>{s.selected?"✓ Include":"＋ Exclude"}</Text></Pressable></View>)}{suggestions.length>0&&<Button title="Match and add selected foods" onPress={addSuggested} styles={styles}/>}</View>
      <View style={card}><Text style={{color:C.ink,fontWeight:"800",fontSize:17}}>{meal} foods ({activeEntries.length})</Text>{activeEntries.length===0&&<Text style={styles.muted}>No foods added to this meal yet.</Text>}{activeEntries.map(e=>{const index=entries.indexOf(e);return <View key={`${e.fdc_id}-${index}`} style={{gap:8,borderTopWidth:1,borderColor:C.border,paddingTop:10}}><Text style={{color:C.ink,fontWeight:"800"}}>{e.description}</Text><Field label="Quantity" value={e.quantity} onChangeText={v=>update(index,"quantity",v)} styles={styles} keyboardType="decimal-pad"/><Text style={styles.label}>Serving unit</Text><View style={{flexDirection:"row",gap:7}}>{e.supported_units.map(u=><Pressable key={u} onPress={()=>update(index,"unit",u)} style={[styles.chip,e.unit===u&&styles.chipOn]}><Text style={styles.chipText}>{u}</Text></Pressable>)}</View><Pressable onPress={()=>{setEntries(x=>x.filter((_,i)=>i!==index));setAnalysis(null)}}><Text style={{color:C.red,fontWeight:"700"}}>Remove food</Text></Pressable></View>})}<Text style={styles.muted}>Manual foods must be selected from USDA search to enable validated nutrient calculations.</Text><Button title="Calculate nutrition and advice" onPress={analyze} styles={styles}/></View>
    </>}
    {view==="results" && <>{!analysis?<View style={card}><Text style={styles.sub}>No result yet. Build meals and calculate an assessment.</Text><Button title="Back to meal plan" onPress={()=>setView("plan")} styles={styles}/></View>:<>
      <View style={card}><Text style={{color:C.ink,fontSize:18,fontWeight:"800"}}>Plan nutrition total</Text><Nutrients summary={analysis.complete_plan_total} colors={C}/><Text style={styles.muted}>Total across selected days. Missing nutrient values can affect totals.</Text></View>
      <View style={card}><Text style={{color:C.ink,fontSize:18,fontWeight:"800"}}>Daily nutrition</Text>{Object.entries(analysis.daily_nutrients||{}).map(([d,summary])=><View key={d} style={{gap:7}}><Text style={{color:C.green,fontWeight:"800"}}>{d}</Text><Nutrients summary={summary} colors={C}/></View>)}</View>
      <View style={card}><Text style={{color:C.ink,fontSize:18,fontWeight:"800"}}>DASH food pattern ideas</Text>{days.map(d=>{const r=dashResults[d];return <View key={d} style={{gap:7}}><Text style={{color:C.green,fontWeight:"800"}}>{d}</Text>{!r?<Text style={styles.muted}>Preparing suggestions…</Text>:r.status==="unavailable"?<Text style={styles.muted}>{r.message}</Text>:r.status!=="optimal"?<Text style={styles.muted}>No reliable set of changes was found.</Text>:<>{(r.changes||[]).slice(0,5).map((change,i)=><Text key={i} style={styles.sub}>• {change.food_group}: {Number(change.current_servings).toFixed(1)} to {Number(change.suggested_servings).toFixed(1)} servings. {change.reason}</Text>)}{r.unmatched_foods?.length>0&&<Text style={styles.muted}>Unmatched foods: {r.unmatched_foods.map(x=>x.food_name).join(", ")}</Text>}<Text style={styles.muted}>{r.ml_preference_model?.used?"Calculated with DASH rules and a learned preference model.":"Calculated using the DASH-based tool."} General ideas, not medical advice.</Text></>}</View>})}</View>
      {Object.entries(analysis.meal_assessments||{}).map(([key,a])=><View key={key} style={card}><Text style={{color:C.ink,fontWeight:"800",fontSize:16}}>{key} · {a.label || "Nutrient-reference assessment"}</Text>{(a.items||[]).map((x,i)=><Text key={i} style={styles.sub}>{x.nutrient}: {x.message}</Text>)}{(a.notes||[]).map((x,i)=><Text key={i} style={styles.muted}>{x}</Text>)}{(a.suggestions||[]).map((s,i)=>{const title=typeof s==="string"?s:s.title; const text=typeof s==="string"?"":s.text;return <View key={i} style={{padding:10,backgroundColor:C.mint,borderRadius:10,gap:5}}><Text style={{color:C.green,fontWeight:"800"}}>{title}</Text><Text style={{color:C.ink,fontSize:12,lineHeight:18}}>{text}</Text><View style={{flexDirection:"row",gap:12}}>{["helpful","not_helpful","tried"].map(r=><Pressable key={r} onPress={()=>feedback(title,r)}><Text style={{color:C.green,fontSize:11,fontWeight:"700"}}>{r.replace("_"," ")}</Text></Pressable>)}</View></View>})}{(a.medication_precautions||[]).map((x,i)=><Text key={i} style={styles.sub}>{typeof x==="string"?x:x.message||x.text}</Text>)}</View>)}<View style={card}><Text style={styles.muted}>{analysis.limitation}</Text></View><Button title="Edit meal plan" onPress={()=>setView("plan")} styles={styles}/></>}</>}
    {view==="history" && <View style={card}><Text style={{color:C.ink,fontSize:18,fontWeight:"800"}}>Meal history</Text>{!history.length&&<Text style={styles.muted}>No saved meal records are available.</Text>}{history.map((r,i)=><View key={r.record_id||i} style={{borderTopWidth:1,borderColor:C.border,paddingTop:10,gap:4}}><Text style={{color:C.ink,fontWeight:"800"}}>{r.meal_date || "Saved meal"}</Text><Text style={styles.muted}>{(r.meals||[]).length} recorded food entries</Text></View>)}</View>}
  </View>;
}
function Field({label,styles,...props}) { return <View><Text style={styles.label}>{label}</Text><TextInput {...props} placeholderTextColor="#99A39C" style={styles.input}/></View>; }
function Button({title,onPress,styles,flex}) { return <Pressable onPress={onPress} style={[styles.button,flex&&{flex:1}]}><Text style={styles.buttonText}>{title}</Text></Pressable>; }
function Nutrients({summary={},colors:C}) { const items=[["energy_kcal","Calories","kcal"],["sodium_mg","Sodium","mg"],["potassium_mg","Potassium","mg"],["protein_g","Protein","g"],["carbs_g","Carbohydrates","g"],["sat_fat_g","Fat","g"]]; return <View style={{flexDirection:"row",flexWrap:"wrap",gap:7}}>{items.map(([key,label,unit])=><View key={key} style={{width:"47%",flexGrow:1,backgroundColor:C.bg,borderRadius:9,padding:9}}><Text style={{color:C.muted,fontSize:10}}>{label}</Text><Text style={{color:C.ink,fontSize:16,fontWeight:"800"}}>{summary[key]==null?"Unknown":`${Number(summary[key]).toLocaleString(undefined,{maximumFractionDigits:1})} ${unit}`}</Text></View>)}</View>; }
