import React,{useEffect,useState} from "react";
import {AppShell,PageHeader,KPI,Card,DataTable,Status,MiniChart,NodeGraph} from "@three/ui-core";
import {theme,nav,brand,subtitle} from "./config";

function Dashboard(){return <><PageHeader title="仪表盘" description="项目、质量、领域、工具和交付概览" action="+ 新建项目"/><div className="grid kpis"><KPI value="12" label="进行中项目"/><KPI value="3" label="待审核" accent="warning"/><KPI value="98" label="质量评分" accent="success"/><KPI value="24" label="本周完成"/></div><div className="grid two" style={{marginTop:18}}><Card title="最近项目"><div className="list">{["Aurora 品牌升级","Nebula App","Motion Reel 2024","Spatial Exhibit"].map((x,i)=><div className="list-row" key={x}><span>{x}</span><small>{["Branding","UI/UX","Motion","3D"][i]}</small></div>)}</div></Card><Card title="质量趋势"><MiniChart values={[62,68,71,74,79,82,88,90,94,98]}/></Card></div></>}
function Projects(){return <><PageHeader title="项目" description="项目状态、领域、负责人、版本和质量" action="+ 新建项目"/><Card><DataTable headers={["项目","领域","状态","负责人","质量","更新时间"]} rows={[["Aurora 品牌升级","Branding",<Status tone="info">进行中</Status>,"Alex","96","今天"],["Nebula App","UI/UX",<Status tone="warning">评审中</Status>,"Taylor","92","昨天"],["Motion Reel 2024","Motion",<Status>已完成</Status>,"Jordan","98","3天前"]]}/></Card></>}
function Research(){return <><PageHeader title="研究洞察" description="趋势、用户、竞品、案例、法规与证据"/><div className="grid three">{["趋势洞察","用户研究","竞品分析","行业报告","案例库","合规知识"].map(x=><Card title={x} key={x}><p style={{color:"var(--muted)"}}>研究结果、数据证据与设计决策依据。</p></Card>)}</div></>}
function BrandSystems(){return <><PageHeader title="品牌系统" description="Logo、色彩、字体、图形、模板和资产"/><div className="grid three">{["Logo","Color","Typography","Icon","Graphic Language","Templates"].map(x=><Card title={x} key={x}><div style={{height:120,border:"1px dashed var(--border)",borderRadius:10}}/></Card>)}</div></>}
function Domains(){return <><PageHeader title="设计领域" description="专业领域能力模块"/><div className="grid three">{["Branding","UI/UX","E-commerce","Spatial","3D","Motion","Video","Audio","Research"].map(x=><Card title={x} key={x}><p style={{color:"var(--muted)"}}>专业能力、模板、工具与案例。</p></Card>)}</div></>}
function Preflight(){return <><PageHeader title="预检 / QA" description="尺寸、字体、图片、版权、色彩、导出与合规" action="运行预检"/><Card><DataTable headers={["检查项","类别","结果","建议","定位"]} rows={[["图片分辨率","资产",<Status>通过</Status>,"—","12 assets"],["字体缺失","字体",<Status tone="warning">警告</Status>,"替换或嵌入","Page 04"],["出血设置","印刷",<Status tone="error">错误</Status>,"增加 3mm","Poster A2"]]}/></Card></>}
function GenericDL({title}:{title:string}){return <><PageHeader title={title} description="AI-native 设计生产与交付模块" action="主要操作"/><div className="grid three">{["概览","资源","活动"].map(x=><Card title={x} key={x}><div className="list">{[1,2,3,4].map(i=><div className="list-row" key={i}><span>{x} Item {i}</span><small>Ready</small></div>)}</div></Card>)}</div></>}

function getHash(){return location.hash.replace("#/","")||nav[0].id;}
export default function App(){
 const [active,setActive]=useState(getHash());
 useEffect(()=>{const fn=()=>setActive(getHash());window.addEventListener("hashchange",fn);return()=>window.removeEventListener("hashchange",fn);},[]);
 const go=(id:string)=>{location.hash="#/"+id;setActive(id);};
 const renderPage=()=>{switch(active){case "dashboard":return <Dashboard/>;case "projects":return <Projects/>;case "research":return <Research/>;case "brand":return <BrandSystems/>;case "domains":return <Domains/>;case "preflight":return <Preflight/>;case "tools":return <GenericDL title="创作工具"/>;case "deliverables":return <GenericDL title="交付中心"/>;case "evidence":return <GenericDL title="证据系统"/>;case "collab":return <GenericDL title="团队协作"/>;default:return <GenericDL title="系统设置"/>;}};
 return <AppShell brand={brand} subtitle={subtitle} theme={theme as any} nav={nav as any} active={active} onNavigate={go}>{renderPage()}</AppShell>;
}
