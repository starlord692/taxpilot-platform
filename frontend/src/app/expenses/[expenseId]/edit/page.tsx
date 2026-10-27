import{ExpenseForm}from"@/components/expenses/expense-form";export default async function Page({params}:{params:Promise<{expenseId:string}>}){return <ExpenseForm id={(await params).expenseId}/>}
