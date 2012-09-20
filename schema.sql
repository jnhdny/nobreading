drop table if exists users;
create table users (
    uid integer primary key autoincrement,
    username string not null,
    password string not null,
    fullname string,
    passwordhash string,
    approver integer,
    foreign key (approver) references users(uid)
);

drop table if exists categories;
create table categories (
    catid integer primary key autoincrement,
    name string not null
);

drop table if exists assets;
create table assets (
    tagno integer primary key,
    model string,
    category integer not null,
    foreign key (category) references categories(catid)
);

drop table if exists consumables;
create table consumables (
    consumableid integer primary key autoincrement,
    name string not null
);

drop table if exists bookings;
create table bookings (
    bookingid integer primary key autoincrement,
    venue string not null,
    startdate integer not null,
    enddate integer not null,
    status integer not null
);

drop table if exists assetbookings;
create table assetbookings (
    abid integer primary key autoincrement,
    asset integer not null,
    booking integer not null,
    foreign key (asset) references assets(tagno),
    foreign key (booking) references bookings(bookingid)
);
